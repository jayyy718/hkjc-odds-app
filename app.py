import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone

# ===================== V1.49 (HKJC Card + STHeadline LiveBet) =====================
# 排位表：HKJC 資訊網 (V1.41 核心)
# 賠率：頭條日報「大票房」頁面 (racing.stheadline.com/tc/odds_livebet/大票房)

st.set_page_config(page_title="賽馬智腦 V1.49", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 排位表 (HKJC) -----------------
@st.cache_data(ttl=600)
def fetch_race_card_v141(date_str, race_no):
    """從 HKJC 資訊網抓取排位"""
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        dfs = pd.read_html(resp.text)
        target_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > max_rows and ('馬名' in df.columns or '馬號' in df.columns):
                target_df = df
                max_rows = len(df)
        
        if not target_df.empty:
            if '馬號' in target_df.columns:
                target_df['馬號'] = pd.to_numeric(target_df['馬號'], errors='coerce')
            return target_df, "HKJC 排位下載成功"
        return pd.DataFrame(), "錯誤: 找不到排位表"
    except Exception as e:
        return pd.DataFrame(), f"排位連線錯誤: {str(e)}"

# ----------------- 2. 即時賠率 (頭條大票房) -----------------
def fetch_odds_livebet(race_no):
    """
    從頭條日報「大票房」抓取賠率
    URL: https://racing.stheadline.com/tc/odds_livebet/大票房?raceno=1
    """
    url = f"https://racing.stheadline.com/tc/odds_livebet/大票房?raceno={race_no}"
    log = [f"大票房連線: {url}"]
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://racing.stheadline.com/"
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return {}, "\n".join(log) + f"\nHTTP 錯誤: {resp.status_code}"
            
        # 嘗試解析 HTML
        # 大票房頁面可能有特殊的表格結構
        try:
            dfs = pd.read_html(resp.text)
        except ValueError:
            return {}, "\n".join(log) + "\n錯誤: Pandas 未能在頁面上找到表格 (可能數據是動態加載的)"
            
        log.append(f"找到 {len(dfs)} 個表格")
        
        odds_map = {}
        target_df = pd.DataFrame()
        
        # 策略：遍歷所有表格，尋找包含賠率的
        # 頭條的賠率表通常包含 "馬號" (或 No) 和 "獨贏" (或 Win)
        
        for i, df in enumerate(dfs):
            # 清理欄位
            df.columns = [str(c).strip() for c in df.columns]
            
            # 記錄欄位以便除錯
            # log.append(f"表格 {i} 欄位: {list(df.columns)}")
            
            # 檢查關鍵字
            has_no = any(x in str(df.columns) for x in ["馬號", "No", "NO"])
            has_win = any(x in str(df.columns) for x in ["獨贏", "Win", "WIN", "賠率"])
            
            if has_no and has_win:
                target_df = df
                log.append(f"鎖定表格 {i} 為賠率表")
                break
                
        if not target_df.empty:
            # 解析數據
            # 找出對應的欄位名
            col_no = next(c for c in target_df.columns if c in ["馬號", "No", "NO"])
            col_win = next(c for c in target_df.columns if c in ["獨贏", "Win", "WIN", "賠率"])
            
            for _, row in target_df.iterrows():
                try:
                    # 嘗試提取馬號
                    h_no = int(row[col_no])
                    h_odds = row[col_win]
                    
                    # 簡單過濾無效數據
                    if str(h_odds).strip() != "-" and str(h_odds).strip() != "":
                        odds_map[h_no] = h_odds
                except: continue
            
            if odds_map:
                log.append(f"成功解析 {len(odds_map)} 筆賠率")
                return odds_map, "\n".join(log)
            else:
                return {}, "\n".join(log) + "\n解析表格但無有效數據"
        else:
            # 備用策略：如果找不到標準表格，嘗試從網頁原始碼中硬抓 (Regex)
            # 因為有些即時賠率是用 DIV 畫的，不是 Table
            log.append("未找到標準表格，嘗試 Regex 暴力搜索...")
            
            # 尋找類似 "馬號": 1, "賠率": 2.5 的結構 (這取決於網頁原始碼)
            # 這裡假設它是簡單的 HTML 結構 <td>1</td>...<td>2.5</td>
            # 但這比較不穩定，先回報失敗
            return {}, "\n".join(log) + "\n錯誤: 未找到包含「馬號」與「獨贏」的表格"

    except Exception as e:
        return {}, "\n".join(log) + f"\n解析錯誤: {str(e)}"

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.49 (大票房版)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 執行面板")
    date_in = st.text_input("日期", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 啟動抓取", type="primary"):
        with st.status("系統運行中...", expanded=True) as status:
            # 1. 抓排位
            st.write("1. 下載 HKJC 排位表...")
            df, msg_card = fetch_race_card_v141(date_in, race_in)
            
            if not df.empty:
                # 2. 抓大票房
                st.write("2. 連線頭條日報「大票房」...")
                odds_map, msg_odds = fetch_odds_livebet(race_in)
                
                # 3. 合併
                if odds_map:
                    st.write("3. 數據對接成功！")
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                    status.update(label="完成", state="complete")
                else:
                    st.warning("大票房頁面未回傳表格，可能數據是動態加載的")
                    df["獨贏"] = "未開盤"
                    status.update(label="無賠率", state="error")
                
                st.session_state['df_149'] = df
                st.session_state['log_149'] = msg_card + "\n\n" + msg_odds
            else:
                st.session_state['log_149'] = msg_card
                status.update(label="排位下載失敗", state="error")

with col2:
    if 'df_149' in st.session_state:
        df = st.session_state['df_149']
        
        # 狀態
        has_odds = any(x != "未開盤" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 已成功從大票房獲取賠率")
        else:
            st.warning("🟡 僅顯示排位 (無法從大票房解析賠率)")
            
        # 表格
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final_cols = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final_cols], use_container_width=True, hide_index=True)
        
        with st.expander("技術日誌"):
            st.text(st.session_state['log_149'])
