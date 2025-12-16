import streamlit as st
import pandas as pd
import requests
import re
import json
from datetime import datetime, timedelta, timezone

# ===================== V1.51 (Safe Syntax Version) =====================
st.set_page_config(page_title="賽馬智腦 V1.51", layout="wide")
HKT = timezone(timedelta(hours=8))

# 1. 抓取排位表 (HKJC 資訊網)
def fetch_card(date_str, race_no):
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        dfs = pd.read_html(resp.text)
        target = pd.DataFrame()
        best_len = 0
        
        for df in dfs:
            # 清理欄位名
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > best_len:
                if '馬名' in df.columns or '馬號' in df.columns:
                    target = df
                    best_len = len(df)
        
        if not target.empty:
            if '馬號' in target.columns:
                target['馬號'] = pd.to_numeric(target['馬號'], errors='coerce')
            return target, "排位表下載成功"
            
        return pd.DataFrame(), "找不到排位表"
    except Exception as e:
        return pd.DataFrame(), str(e)

# 2. 抓取賠率 (頭條日報 API)
def fetch_st_odds(date_str, race_no):
    # 格式化日期
    d_fmt = date_str.replace("/", "-")
    
    # 目標 1: 標準賠率頁 (通常是靜態表格)
    url1 = f"https://racing.stheadline.com/racing/race-odds.php?date={d_fmt}&race_no={race_no}"
    
    # 目標 2: 大票房 API (嘗試猜測)
    url2 = f"https://racing.stheadline.com/tc/odds_livebet/get_odds_json.php?date={d_fmt}&raceno={race_no}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://racing.stheadline.com/"
    }
    
    log = []
    odds = {}
    
    # --- 嘗試方法 1: Pandas 讀取標準頁 ---
    try:
        log.append(f"嘗試讀取標準頁: {url1}")
        resp = requests.get(url1, headers=headers, timeout=8)
        resp.encoding = "utf-8"
        
        dfs = pd.read_html(resp.text)
        for df in dfs:
            df.columns = [str(c).strip() for c in df.columns]
            if "馬號" in df.columns and "獨贏" in df.columns:
                log.append("成功解析 HTML 表格")
                for i, row in df.iterrows():
                    try:
                        odds[int(row["馬號"])] = row["獨贏"]
                    except: pass
                return odds, "\n".join(log)
    except:
        log.append("標準頁讀取失敗")

    # --- 嘗試方法 2: 直接請求 JSON API ---
    if not odds:
        try:
            log.append(f"嘗試 API: {url2}")
            resp = requests.get(url2, headers=headers, timeout=8)
            if resp.status_code == 200:
                # 嘗試當作 JSON 解析
                try:
                    data = resp.json()
                    # 假設 data 是一個列表
                    if isinstance(data, list):
                        for item in 
                            # 嘗試各種可能的 key
                            h = item.get('horse_no')
                            if not h: h = item.get('no')
                            
                            w = item.get('win')
                            if not w: w = item.get('odds')
                            
                            if h and w:
                                odds[int(h)] = w
                except:
                    log.append("JSON 解析失敗")
        except:
            log.append("API 連線失敗")

    # --- 嘗試方法 3: Regex 暴力搜尋 ---
    if not odds:
        log.append("嘗試正則表達式搜尋...")
        # 模擬搜尋 "win_odds": "2.5" 這種模式
        matches = re.findall(r'"win_odds"\s*:\s*"(\d+\.?\d*)"', resp.text)
        if matches:
            # 如果只找到賠率但沒馬號，這招通常沒用，所以這裡只是一個備案
            pass
            
    if odds:
        return odds, "\n".join(log)
    else:
        return {}, "\n".join(log) + "\n無賠率數據 (可能未開盤)"

# UI 介面
st.title("🏇 賽馬智腦 V1.51 (結構修復版)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    date_val = st.text_input("日期", value=def_date)
    race_val = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 執行", type="primary"):
        with st.status("運行中...", expanded=True) as s:
            st.write("1. 下載排位...")
            df, msg1 = fetch_card(date_val, race_val)
            
            msg2 = ""
            if not df.empty:
                st.write("2. 下載賠率...")
                odds, msg2 = fetch_st_odds(date_val, race_val)
                
                if odds:
                    df["獨贏"] = df["馬號"].map(odds).fillna("未開盤")
                    s.update(label="成功", state="complete")
                else:
                    df["獨贏"] = "未開盤"
                    s.update(label="無賠率", state="error")
                
                st.session_state['df'] = df
                st.session_state['log'] = msg1 + "\n\n" + msg2
            else:
                st.session_state['log'] = msg1
                s.update(label="排位下載失敗", state="error")

with col2:
    if 'df' in st.session_state:
        df = st.session_state['df']
        
        # 顯示
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final], use_container_width=True, hide_index=True)
        
        with st.expander("日誌"):
            st.text(st.session_state['log'])
