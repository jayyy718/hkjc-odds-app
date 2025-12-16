import streamlit as st
import pandas as pd
import requests
import re
import json
from datetime import datetime, timedelta, timezone

# ===================== V1.45 (Best RaceCard + JSON App Odds) =====================
# 排位表：使用 V1.41 的 Pandas 暴力解析法 (racing.hkjc.com) - 已驗證最穩定
# 賠率：使用 HKJC App 的後端 JSON 接口 (扮成手機 App 取數據)

st.set_page_config(page_title="賽馬智腦 V1.45", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 排位表抓取 (V1.41 核心邏輯) -----------------
def fetch_race_card_v141(date_str, race_no):
    """
    從 racing.hkjc.com 資訊網抓取排位表
    """
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    log = [f"排位表連線: {url}"]
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if "沒有相符的資料" in resp.text:
            return pd.DataFrame(), "\n".join(log) + "\n官方回傳無資料"

        dfs = pd.read_html(resp.text)
        
        # 挑選最大的表格
        target_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            
            if len(df) > max_rows:
                # 簡單檢查是否像排位表
                if '馬名' in df.columns or '馬號' in df.columns or 'Horse' in df.columns:
                    target_df = df
                    max_rows = len(df)
        
        if not target_df.empty:
            log.append(f"成功鎖定排位表，共 {len(target_df)} 匹")
            # 確保馬號是數字類型，方便後續合併
            if '馬號' in target_df.columns:
                target_df['馬號'] = pd.to_numeric(target_df['馬號'], errors='coerce')
            return target_df, "\n".join(log)
            
        return pd.DataFrame(), "\n".join(log) + "\n找不到排位表格"

    except Exception as e:
        return pd.DataFrame(), "\n".join(log) + f"\n排位表錯誤: {str(e)}"

# ----------------- 2. 賠率抓取 (App JSON 接口) -----------------
def fetch_odds_json(race_no):
    """
    嘗試從 bet.hkjc.com 的 JSON 接口獲取賠率
    這個接口通常比網頁版更穩定，因為它是給 AJAX 用的
    """
    # 注意：這個 JSON 接口通常不需要日期，它只回傳「當前最近賽事」的賠率
    # 如果今天是週二，它可能回傳空的，或者是明天第一場的數據
    
    url = "https://bet.hkjc.com/racing/jsonData.aspx"
    # 參數：type=winodds (獨贏賠率)
    params = {
        "type": "winodds",
        "date": datetime.now(HKT).strftime("%Y-%m-%d"), 
        "venue": "HV", # 跑馬地
        "start": race_no,
        "end": race_no
    }
    
    log = [f"賠率連線 (JSON): {url}"]
    odds_map = {}
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Referer": "https://bet.hkjc.com/racing/"
        }
        
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        
        if resp.status_code == 200:
            txt = resp.text
            # 這個 JSON 的格式非常奇怪，有時候是 "1"="2.3"; "2"="4.5";
            # 有時候是標準 JSON {"1": "2.3", ...}
            
            # 方法 A: 正則表達式抓取 "馬號"="賠率"
            matches = re.findall(r'(\d+)\s*=\s*(\d+\.\d+)', txt)
            for m in matches:
                odds_map[int(m[0])] = m[1]
                
            # 方法 B: 正則抓取 JSON 格式 "1":"2.3"
            if not odds_map:
                matches = re.findall(r'"(\d+)"\s*:\s*"(\d+\.\d+)"', txt)
                for m in matches:
                    odds_map[int(m[0])] = m[1]
            
            if odds_map:
                log.append(f"成功獲取 {len(odds_map)} 筆賠率")
            else:
                log.append(f"回應內容 (前100字): {txt[:100]}...")
                log.append("解析後無賠率數據 (可能未開盤)")
        else:
            log.append(f"HTTP 錯誤: {resp.status_code}")
            
    except Exception as e:
        log.append(f"賠率錯誤: {str(e)}")
        
    return odds_map, "\n".join(log)

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.45 (V1.41排位 + JSON賠率)")

# 自動設定日期
now = datetime.now(HKT)
# 預設抓明天 (如果是週二)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 🛠️ 執行")
    date_in = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 執行", type="primary"):
        # 1. 先抓排位 (我們知道這個一定行)
        with st.status("正在讀取數據...", expanded=True) as status:
            st.write("正在下載排位表 (V1.41 核心)...")
            df, log_card = fetch_race_card_v141(date_in, race_in)
            
            if not df.empty:
                st.write("排位表下載成功，正在尋找賠率...")
                # 2. 抓賠率
                odds_map, log_odds = fetch_odds_json(race_in)
                
                # 3. 合併
                if odds_map:
                    st.write("賠率獲取成功，正在合併...")
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                else:
                    st.write("暫無賠率數據，顯示「未開盤」")
                    df["獨贏"] = "未開盤"
                
                st.session_state['df_145'] = df
                st.session_state['log_145'] = log_card + "\n\n" + log_odds
                status.update(label="完成", state="complete")
            else:
                st.session_state['log_145'] = log_card
                status.update(label="排位表下載失敗", state="error")

with col2:
    if 'df_145' in st.session_state:
        df = st.session_state['df_145']
        
        st.subheader(f"第 {race_in} 場賽事")
        
        # 檢查是否有賠率
        has_odds = any(x != "未開盤" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 賠率已更新")
        else:
            st.warning("🟡 僅顯示排位 (賠率未開盤)")
            
        # 顯示
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位', '排位體重']
        final_cols = [c for c in cols if c in df.columns]
        
        st.dataframe(
            df[final_cols], 
            use_container_width=True, 
            hide_index=True
        )
        
        with st.expander("查看日誌"):
            st.text(st.session_state['log_145'])
