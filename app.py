import streamlit as st
import pandas as pd
import requests
import re
import json
from datetime import datetime, timedelta, timezone

# ===================== V1.50 (API Sniffer) =====================
# 排位表：HKJC 資訊網 (V1.41 核心)
# 賠率：直接呼叫頭條日報的後端 API (繞過動態網頁)

st.set_page_config(page_title="賽馬智腦 V1.50", layout="wide")
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

# ----------------- 2. 賠率 API 狙擊 (頭條日報) -----------------
def fetch_stheadline_api(date_str, race_no):
    """
    嘗試直接打擊頭條日報的數據接口
    """
    # 格式化日期 YYYY-MM-DD
    date_fmt = date_str.replace("/", "-")
    
    # 潛在的 API 列表 (這些是動態網頁常用的後端)
    urls_to_try = [
        # 1. 大票房專用 API (推測)
        f"https://racing.stheadline.com/tc/odds_livebet/get_odds_json.php?date={date_fmt}&raceno={race_no}",
        # 2. 標準賠率頁面 (雖然是 PHP 但有時內嵌 JSON)
        f"https://racing.stheadline.com/racing/race-odds.php?date={date_fmt}&race_no={race_no}"
    ]
    
    log = []
    odds_map = {}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest", # 偽裝成 AJAX 請求
        "Referer": "https://racing.stheadline.com/tc/odds_livebet/%E5%A4%A7%E7%A5%A8%E6%88%BF"
    }
    
    for url in urls_to_try:
        log.append(f"嘗試 API: {url}")
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            
            if resp.status_code != 200:
                log.append(f"-> 失敗: HTTP {resp.status_code}")
                continue
                
            # 策略 A: 嘗試直接解析 JSON
            try:
                data = resp.json()
                log.append("-> 成功獲取 JSON 格式數據")
                # 這裡需要根據實際回傳結構解析，假設是列表或字典
                # ST Headline 結構通常比較亂，我們用遞迴搜尋 "win" 或 "odds"
                # 這裡先做簡單處理
                if isinstance(data, list):
                    for item in 
                        h = item.get('horse_no') or item.get('no')
                        w = item.get('win') or item.get('odds')
                        if h and w: odds_map[int(h)] = w
                elif isinstance(data, dict):
                     # 可能是 { "1": {"win": 2.3}, "2": ... }
                     for k, v in data.items():
                         if isinstance(v, dict):
                             w = v.get('win') or v.get('odds')
                             if w: odds_map[int(k)] = w
                
                if odds_map: break # 成功就跳出
                
            except:
                log.append("-> 非標準 JSON，轉用 Regex 搜尋")
                
            # 策略 B: 既然不是純 JSON，可能是 HTML 裡面包了 Javascript 變數
            # 尋找 "win": 2.3 或 similar patterns
            # 範例: "horse_no":1,"win_odds":"2.6"
            
            # 模式 1: "win_odds":"2.6"
            matches = re.findall(r'"win_odds"\s*:\s*"(\d+\.?\d*)"', resp.text)
            if not matches:
                 # 模式 2: html 表格內的數據 <td>99</td> (如果不小心抓到 HTML)
                 pass
            
            # 還是找不到? 嘗試最暴力的 Regex
            # 尋找所有數字對 (馬號, 賠率)
            # 假設馬號 1-14，賠率 1.0-999.0
            # 這在 HTML 源碼中通常表現為: <td>1</td>...<td>2.4</td>
            
            # 讓我們回退一步：如果 API 失敗，我們試試看能不能抓到 "標準版" 的表格
            # 因為用戶說大票房有更新，標準版通常也會同步
            if "race-odds.php" in url:
                try:
                    dfs = pd.read_html(resp.text)
                    for df in dfs:
                        df.columns = [str(c).strip() for c in df.columns]
                        if "馬號" in df.columns and "獨贏" in df.columns:
                            log.append("-> 透過 Pandas 找到表格！")
                            for _, row in df.iterrows():
                                try:
                                    odds_map[int(row["馬號"])] = row["獨贏"]
                                except: pass
                            break
                except: pass
                
            if odds_map: break

        except Exception as e:
            log.append(f"-> 錯誤: {str(e)}")
            
    return odds_map, "\n".join(log)

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.50 (API 狙擊)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 執行面板")
    date_in = st.text_input("日期", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 啟動", type="primary"):
        with st.status("正在連線...", expanded=True) as status:
            # 1. 抓排位
            st.write("下載 HKJC 排位表...")
            df, msg_card = fetch_race_card_v141(date_in, race_in)
            
            if not df.empty:
                # 2. 抓賠率
                st.write("正在搜尋頭條日報數據源...")
                odds_map, msg_odds = fetch_stheadline_api(date_in, race_in)
                
                if odds_map:
                    st.write(f"成功獲取 {len(odds_map)} 筆賠率！")
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                    status.update(label="成功", state="complete")
                else:
                    st.warning("無法從後端接口獲取賠率")
                    df["獨贏"] = "未開盤"
                    status.update(label="無賠率數據", state="error")
                
                st.session_state['df_150'] = df
                st.session_state['log_150'] = msg_card + "\n\n" + msg_odds
            else:
                st.session_state['log_150'] = msg_card
                status.update(label="排位下載失敗", state="error")

with col2:
    if 'df_150' in st.session_state:
        df = st.session_state['df_150']
        
        has_odds = any(x != "未開盤" and x != "-" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 賠率已更新")
        else:
            st.warning("🟡 暫無賠率 (API 未回傳有效數據)")
            
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final_cols = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final_cols], use_container_width=True, hide_index=True)
        
        with st.expander("API 日誌"):
            st.text(st.session_state['log_150'])
