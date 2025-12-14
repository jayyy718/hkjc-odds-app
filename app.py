import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (強力穩定版)")
st.caption("數據源：51saima (每5分鐘更新)")

# 自動刷新
count = st_autorefresh(interval=300000, limit=None, key="auto")

# 側邊欄
total_races = st.sidebar.number_input("今日場數", 1, 14, 10)
st.sidebar.write(f"更新時間: {datetime.now().strftime('%H:%M:%S')}")

# ===================== 抓取核心 =====================
def fetch_race_data(race_no, retries=3):
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    
    # 模擬更真實的 Header
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.51saima.com/mobi/index.jsp"
    }
    
    for i in range(retries):
        try:
            # 增加 timeout, 防止網路慢
            r = requests.get(url, headers=headers, timeout=15)
            r.encoding = 'utf-8' # 強制編碼
            
            if r.status_code != 200:
                time.sleep(1)
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            
            # --- 暴力解析法 ---
            tds = soup.find_all("td")
            if not tds:
                time.sleep(1)
                continue # 如果沒抓到格子，重試
                
            rows = []
            idx = 0
            while idx < len(tds) - 2:
                try:
                    t1 = tds[idx].get_text(strip=True)
                    t2 = tds[idx+1].get_text(strip=True)
                    t3 = tds[idx+2].get_text(strip=True)
                    
                    if t1.isdigit():
                        no = int(t1)
                        # 過濾掉奇怪的長數字
                        if no > 20: 
                            idx += 1
                            continue
                            
                        # 賠率清洗：找數字
                        odds_match = re.findall(r"\d+\.\d+", t3)
                        if odds_match:
                            val = float(odds_match[0])
                            rows.append({
                                "RaceID": race_no,
                                "HorseNo": no,
                                "HorseName": t2,
                                "Odds": val
                            })
                except: pass
                idx += 1
            
            if rows:
                # 成功抓到數據，去重並回傳
                df = pd.DataFrame(rows)
                df = df.drop_duplicates(subset=["HorseNo"], keep="last")
                # 簡單驗證：一場比賽通常至少有 5 隻馬
                if len(df) >= 5:
                    return df
            
            # 如果抓到的馬太少，可能網頁沒載入完，等待後重試
            time.sleep(1)
            
        except Exception as e:
            time.sleep(1)
            
    return pd.DataFrame() # 真的失敗回傳空

# ===================== 主程序 =====================
if st.button("手動刷新"): st.rerun()

all_data = []
status_text = st.empty()
progress_bar = st.progress(0)

# 使用 Session State 來保存數據，防止刷新時閃爍
if 'last_data' not in st.session_state:
    st.session_state.last_data = pd.DataFrame()

with st.spinner("正在連線至 51saima..."):
    temp_data = []
    for i in range(1, total_races + 1):
        status_text.text(f"正在讀取第 {i} 場賠率...")
        df = fetch_race_data(i)
        if not df.empty:
            temp_data.append(df)
        # 稍微暫停一下，避免對網站請求太快被擋
        time.sleep(0.5) 
        progress_bar.progress(i / total_races)

status_text.empty()
progress_bar.empty()

# 如果抓到新數據，更新 Session
if temp_
    df_all = pd.concat(temp_data, ignore_index=True)
    st.session_state.last_data = df_all
    st.success(f"更新成功！共獲取 {len(df_all)} 匹馬數據。")
else:
    if not st.session_state.last_data.empty:
        st.warning("本次更新未獲取新數據，顯示上一次的緩存。")
    else:
        st.error("無法獲取數據。請稍後再試。")

# 顯示分析結果 (使用 session_state 中的數據)
if not st.session_state.last_data.empty:
    df_show = st.session_state.last_data.copy()
    
    st.divider()
    col1, col2 = st.columns(2)
    mult = col1.slider("模擬變動(%)", 0, 50, 15)
    thresh = col2.slider("落飛門檻(%)", 0, 30, 5)
    
    df_show["Last"] = df_show["Odds"]
    df_show["First"] = (df_show["Odds"] * (1 + mult/100)).round(1)
    df_show["Drop"] = ((df_show["First"] - df_show["Last"]) / df_show["First"] * 100).round(1)
    
    def get_sig(row):
        if row["Last"] <= 10 and row["Drop"] > thresh:
            return "🔥" if row["First"] > 10 else "✅"
        return ""
        
    df_show["Sig"] = df_show.apply(get_sig, axis=1)
    res = df_show[df_show["Sig"] != ""]
    
    if not res.empty:
        res = res.sort_values(by=["RaceID", "HorseNo"])
        st.dataframe(res, use_container_width=True)
    else:
        st.info("暫無落飛馬")


