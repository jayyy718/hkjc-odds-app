import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.42 (Dual Fetch: Info + Odds) =====================
# 雙重抓取模式：
# 1. 抓取 RaceCard (排位表) -> 獲取馬號、馬名、騎師、檔位
# 2. 抓取 Odds (賠率表) -> 獲取獨贏、位置賠率
# 3. 合併顯示

st.set_page_config(page_title="賽馬智腦 V1.42", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 核心邏輯 -----------------

def get_next_race_date():
    """預設抓取週三或賽事日"""
    today = datetime.now(HKT)
    # 簡單邏輯：週二就抓明天(週三)
    if today.weekday() == 1: 
        next_r = today + timedelta(days=1)
        return next_r.strftime("%Y/%m/%d"), f"{next_r.strftime('%Y-%m-%d')} (週三)"
    return today.strftime("%Y/%m/%d"), today.strftime("%Y-%m-%d")

def fetch_table_via_pandas(url, keyword_check=None):
    """通用函數：給網址，回傳最像樣的表格"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        
        if "沒有相符的資料" in resp.text:
            return None, "官方回傳無資料"

        dfs = pd.read_html(resp.text)
        
        # 挑選最好的表格
        best_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            
            # 如果指定了關鍵字，必須包含該欄位
            if keyword_check and keyword_check not in df.columns:
                continue
                
            if len(df) > max_rows:
                best_df = df
                max_rows = len(df)
                
        return best_df, f"成功解析，共 {len(best_df)} 筆"
    except Exception as e:
        return None, str(e)

def fetch_combined_data(date_str, race_no):
    log = []
    
    # 1. 抓取排位表 (Race Card) - 負責靜態資料
    url_card = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    df_card, msg_card = fetch_table_via_pandas(url_card, keyword_check="馬名")
    log.append(f"排位表: {msg_card}")
    
    # 2. 抓取賠率表 (Odds) - 負責動態賠率
    url_odds = f"https://racing.hkjc.com/racing/information/Chinese/Racing/Odds/WinPlaceAndWB.aspx?RaceDate={date_str}&RaceNo={race_no}"
    df_odds, msg_odds = fetch_table_via_pandas(url_odds, keyword_check="獨贏")
    log.append(f"賠率表: {msg_odds}")
    
    # 3. 合併邏輯
    if df_card is not None and not df_card.empty:
        # 確保有馬號欄位，轉為整數以方便合併
        if '馬號' in df_card.columns:
            # 處理馬號可能有 "*" 或其他符號的情況
            df_card['JoinKey'] = pd.to_numeric(df_card['馬號'], errors='coerce')
        
        # 處理賠率表
        if df_odds is not None and not df_odds.empty:
            if '馬號' in df_odds.columns:
                df_odds['JoinKey'] = pd.to_numeric(df_odds['馬號'], errors='coerce')
                
                # 只保留賠率相關欄位，避免欄位重複
                cols_to_use = ['JoinKey']
                if '獨贏' in df_odds.columns: cols_to_use.append('獨贏')
                if '位置' in df_odds.columns: cols_to_use.append('位置')
                
                df_odds_clean = df_odds[cols_to_use]
                
                # 合併！ (Left Join: 以排位表為主)
                df_final = pd.merge(df_card, df_odds_clean, on='JoinKey', how='left')
                
                # 填充空值
                df_final['獨贏'] = df_final['獨贏'].fillna("未開盤")
                df_final['位置'] = df_final['位置'].fillna("-")
                
                return df_final, "\n".join(log)
        
        # 如果抓不到賠率表 (可能未開盤)，直接回傳排位表，並補上「未開盤」
        df_card['獨贏'] = "未開盤"
        df_card['位置'] = "-"
        return df_card, "\n".join(log)
        
    return pd.DataFrame(), "\n".join(log)

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.42 (雙核心抓取)")

d_str, d_lbl = get_next_race_date()
st.info(f"📅 目標賽事: **{d_lbl}**")

col1, col2 = st.columns([1, 2])

with col1:
    user_date = st.text_input("日期 (YYYY/MM/DD)", value=d_str)
    race_no = st.selectbox("場次", range(1, 15))
    
    if st.button("🔄 獲取排位 + 即時賠率", type="primary"):
        with st.spinner("雙線程讀取中 (排位表 + 賠率表)..."):
            df, log = fetch_combined_data(user_date, race_no)
            st.session_state['data_142'] = df
            st.session_state['log_142'] = log

with col2:
    if 'data_142' in st.session_state:
        df = st.session_state['data_142']
        log = st.session_state['log_142']
        
        if not df.empty:
            # 判斷是否真的有賠率數據 (不是 "未開盤")
            has_odds = False
            if '獨贏' in df.columns:
                # 檢查是否含有數字
                sample = str(df['獨贏'].iloc[0])
                if any(char.isdigit() for char in sample):
                    has_odds = True
            
            status_icon = "🟢" if has_odds else "🟡"
            status_text = "賠率已更新" if has_odds else "等待官方開盤 (已顯示排位)"
            
            st.subheader(f"第 {race_no} 場 | {status_icon} {status_text}")
            
            # 顯示
            # 挑選欄位
            show_cols = ['馬號', '馬名', '獨贏', '位置', '騎師', '練馬師', '檔位']
            final_cols = [c for c in show_cols if c in df.columns]
            
            st.dataframe(df[final_cols], use_container_width=True, hide_index=True)
            
            with st.expander("查看抓取日誌"):
                st.text(log)
        else:
            st.error("查無資料")
            st.text(log)
