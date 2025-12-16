import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

# ===================== V1.44 (SCMP Names + HKJC XML Odds) =====================
# 這是最底層的解決方案：
# 1. SCMP 負責提供馬名、騎師 (靜態網頁，不易被擋，已修正解析 Bug)
# 2. HKJC XML 負責提供即時賠率 (純數據接口，極速且不擋 IP)

st.set_page_config(page_title="賽馬智腦 V1.44", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. HKJC XML 賠率抓取 (核心武器) -----------------
def fetch_hkjc_xml_odds(date_str, venue, race_no):
    """
    直接從馬會舊版接口獲取 XML 格式賠率
    URL: https://bet.hkjc.com/racing/getXML.aspx?type=winplacewb&date=2025-12-17&venue=HV&raceno=1
    """
    # 日期格式必須是 YYYY-MM-DD
    xml_date = date_str.replace("/", "-")
    url = f"https://bet.hkjc.com/racing/getXML.aspx?type=winplacewb&date={xml_date}&venue={venue}&raceno={race_no}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://bet.hkjc.com/"
    }
    
    log = f"XML 連線: {url}\n"
    odds_map = {}
    
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            # 解析 XML
            try:
                root = ET.fromstring(resp.text)
                # 尋找所有馬匹節點
                # 結構通常是 <pool><horse number="1" odds="2.3" ... /></pool>
                count = 0
                for horse in root.findall(".//horse"):
                    h_no = horse.get("number")
                    h_odds = horse.get("odds")
                    
                    if h_no and h_odds:
                        # 處理 "SCR" (退出) 或其他非數字狀態
                        if "SCR" in h_odds:
                            odds_map[int(h_no)] = "退出"
                        else:
                            odds_map[int(h_no)] = h_odds
                        count += 1
                
                if count > 0:
                    log += f"XML 解析成功: 獲取 {count} 筆賠率\n"
                    return odds_map, log
                else:
                    log += "XML 解析成功但無馬匹數據 (可能未開盤)\n"
            except ET.ParseError:
                log += "XML 格式錯誤 (可能非標準響應)\n"
        else:
            log += f"HTTP 錯誤: {resp.status_code}\n"
            
    except Exception as e:
        log += f"XML 連線失敗: {str(e)}\n"
        
    return {}, log

# ----------------- 2. SCMP 馬名抓取 (修正版) -----------------
def fetch_scmp_names_fixed(date_str, race_no):
    """
    修正後的 SCMP 解析器：遍歷所有表格，找出最大的那個
    解決「只抓到 3 隻馬」的問題
    """
    # SCMP 日期格式: YYYYMMDD
    scmp_date = date_str.replace("/", "").replace("-", "")
    url = f"https://racing.scmp.com/racing/race-card/{scmp_date}/race/{race_no}"
    log = f"SCMP 連線: {url}\n"
    
    try:
        # 使用 Pandas 讀取所有表格
        dfs = pd.read_html(url, timeout=10)
        log += f"找到 {len(dfs)} 個表格\n"
        
        target_df = pd.DataFrame()
        max_len = 0
        
        # 尋找真正的主表格 (行數最多，且包含 'Horse' 或 'Jockey')
        for df in dfs:
            # 轉換欄位為字串並大寫
            df.columns = [str(c).upper() for c in df.columns]
            
            # SCMP 的表格特徵
            if len(df) > max_len:
                # 檢查是否有關鍵欄位
                has_horse = any("HORSE" in c for c in df.columns)
                has_no = any("NO." in c for c in df.columns)
                
                if has_horse or has_no:
                    target_df = df
                    max_len = len(df)
        
        if not target_df.empty:
            log += f"鎖定主表格，共 {len(target_df)} 匹馬\n"
            
            # 標準化欄位名稱
            # SCMP 欄位通常是: No., Horse, Jockey, Trainer, ...
            # 我們需要重新命名以方便處理
            
            # 尋找對應欄位索引
            cols = target_df.columns
            rename_map = {}
            
            for c in cols:
                if "NO." in c: rename_map[c] = "馬號"
                elif "HORSE" in c: rename_map[c] = "馬名"
                elif "JOCKEY" in c: rename_map[c] = "騎師"
                elif "TRAINER" in c: rename_map[c] = "練馬師"
                elif "DRAW" in c: rename_map[c] = "檔位"
            
            target_df = target_df.rename(columns=rename_map)
            
            # 簡單清理
            if "馬號" in target_df.columns:
                target_df["馬號"] = pd.to_numeric(target_df["馬號"], errors='coerce')
                target_df = target_df.dropna(subset=["馬號"]) # 移除無效行
                target_df["馬號"] = target_df["馬號"].astype(int)
            
            return target_df, log
        else:
            return pd.DataFrame(), log + "錯誤: 找不到符合條件的主表格\n"
            
    except Exception as e:
        return pd.DataFrame(), log + f"SCMP 解析失敗: {str(e)}\n"

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.44 (協議混合版)")

# 自動計算預設日期 (週二 -> 明天週三)
now = datetime.now(HKT)
if now.weekday() == 1: # 週二
    def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d")
    def_venue = "HV"
else:
    def_date = now.strftime("%Y/%m/%d")
    def_venue = "HV" if now.weekday() == 2 else "ST"

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 📡 數據源設定")
    date_in = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    venue_in = st.radio("場地", ["HV (跑馬地)", "ST (沙田)"], index=0 if def_venue=="HV" else 1, horizontal=True)
    race_in = st.number_input("場次", 1, 14, 1)
    
    venue_code = "HV" if "HV" in venue_in else "ST"
    
    if st.button("🚀 執行混合抓取", type="primary"):
        with st.status("正在執行雙重連線...", expanded=True) as status:
            # 1. 抓 SCMP (馬名)
            st.write("正在自 SCMP 下載排位表...")
            df_scmp, log_scmp = fetch_scmp_names_fixed(date_in, race_in)
            
            # 2. 抓 HKJC XML (賠率)
            st.write("正在自 HKJC 投注伺服器獲取賠率...")
            odds_map, log_xml = fetch_hkjc_xml_odds(date_in, venue_code, race_in)
            
            # 3. 合併
            if not df_scmp.empty:
                st.write("正在合併數據...")
                # 建立賠率欄位
                df_scmp["獨贏賠率"] = df_scmp["馬號"].map(odds_map).fillna("未開盤")
                
                st.session_state['df_144'] = df_scmp
                st.session_state['log_144'] = log_scmp + "\n" + log_xml
                status.update(label="完成", state="complete")
            else:
                st.session_state['log_144'] = log_scmp
                status.update(label="SCMP 抓取失敗", state="error")

with col2:
    if 'df_144' in st.session_state:
        df = st.session_state['df_144']
        log = st.session_state['log_144']
        
        st.subheader(f"第 {race_in} 場賽事詳情")
        
        # 顯示重點欄位
        cols_to_show = ['馬號', '馬名', '獨贏賠率', '騎師', '練馬師', '檔位']
        # 確保欄位存在
        final_cols = [c for c in cols_to_show if c in df.columns]
        
        # 高亮顯示賠率
        st.dataframe(
            df[final_cols],
            column_config={
                "獨贏賠率": st.column_config.TextColumn(
                    "獨贏 (Win)", 
                    help="來自 HKJC XML 實時接口",
                    width="medium"
                ),
                "馬名": st.column_config.TextColumn("馬名 (Horse)", width="large"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # 賠率狀態提示
        has_odds = any(x != "未開盤" and x != "退出" for x in df["獨贏賠率"])
        if has_odds:
            st.success("🟢 已成功連線至 HKJC 投注系統並獲取即時賠率")
        else:
            st.warning("🟡 列表已建立，但 XML 接口暫無賠率數據 (請確認是否已開盤)")
            
    elif 'log_144' in st.session_state:
        st.error("無法建立排位表，請檢查日誌")
        with st.expander("查看日誌"):
            st.text(st.session_state['log_144'])
    else:
        st.info("👈 請點擊左側按鈕開始")
