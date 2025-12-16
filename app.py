import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.52 (Flat Structure) =====================
# 1. 排位表：HKJC 資訊網 (最穩定)
# 2. 賠率：頭條日報「賠率版」 (非大票房，這個頁面通常是靜態的，容易抓)

st.set_page_config(page_title="賽馬智腦 V1.52", layout="wide")
HKT = timezone(timedelta(hours=8))

# --- 獨立函數：解析排位表 ---
def parse_hkjc_card(text):
    """將 HTML 解析為 DataFrame"""
    try:
        dfs = pd.read_html(text)
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            # 判斷是否為排位表
            if '馬名' in df.columns or '馬號' in df.columns:
                if len(df) > 5: # 至少要有幾匹馬
                    return df
    except:
        pass
    return pd.DataFrame()

# --- 獨立函數：解析頭條日報賠率 ---
def parse_st_odds(text):
    """將頭條日報 HTML 解析為賠率字典"""
    odds_map = {}
    try:
        dfs = pd.read_html(text)
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).strip() for c in df.columns]
            
            # 頭條日報標準格式通常有 "馬號" 和 "獨贏"
            if "馬號" in df.columns and "獨贏" in df.columns:
                for idx, row in df.iterrows():
                    try:
                        h_no = int(row["馬號"])
                        h_win = row["獨贏"]
                        odds_map[h_no] = h_win
                    except:
                        continue
                return odds_map
    except:
        pass
    return odds_map

# --- 主流程：下載排位 ---
def fetch_card(date_str, race_no):
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        df = parse_hkjc_card(resp.text)
        if not df.empty:
            if '馬號' in df.columns:
                df['馬號'] = pd.to_numeric(df['馬號'], errors='coerce')
            return df, "HKJC 排位下載成功"
        return pd.DataFrame(), "錯誤：找不到排位表格"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- 主流程：下載賠率 ---
def fetch_odds(date_str, race_no):
    # 改抓頭條日報的「標準賠率頁」，不要抓「大票房」
    # 標準頁通常是純 HTML 表格，Pandas 一定抓得到
    date_fmt = date_str.replace("/", "-")
    url = f"https://racing.stheadline.com/racing/race-odds.php?date={date_fmt}&race_no={race_no}"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        # 讓 requests 自動猜編碼 (頭條有時用 Big5)
        resp.encoding = resp.apparent_encoding
        
        odds_map = parse_st_odds(resp.text)
        
        if odds_map:
            return odds_map, f"成功從頭條日報獲取 {len(odds_map)} 筆賠率"
        else:
            return {}, "錯誤：第三方網站未回傳有效賠率表 (可能未開盤)"
            
    except Exception as e:
        return {}, str(e)

# --- UI ---
st.title("🏇 賽馬智腦 V1.52 (結構修復版)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    date_in = st.text_input("日期", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 執行", type="primary"):
        with st.status("運行中...", expanded=True) as s:
            st.write("1. 下載 HKJC 排位...")
            df, msg1 = fetch_card(date_in, race_in)
            
            if not df.empty:
                st.write("2. 下載頭條日報賠率...")
                odds_map, msg2 = fetch_odds(date_in, race_in)
                
                if odds_map:
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                    s.update(label="成功", state="complete")
                else:
                    df["獨贏"] = "未開盤"
                    s.update(label="無賠率", state="error")
                
                st.session_state['df'] = df
                st.session_state['log'] = msg1 + "\n" + msg2
            else:
                st.session_state['log'] = msg1
                s.update(label="排位表失敗", state="error")

with col2:
    if 'df' in st.session_state:
        df = st.session_state['df']
        
        has_odds = any(x != "未開盤" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 賠率已更新")
        else:
            st.warning("🟡 暫無賠率")
            
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final], use_container_width=True, hide_index=True)
        
        with st.expander("日誌"):
            st.text(st.session_state['log'])
