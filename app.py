import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# 設定頁面
st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析")
count = st_autorefresh(interval=300000, limit=None, key="auto")

# 側邊欄
total_races = st.sidebar.number_input("場數", 1, 14, 10)
st.sidebar.write(f"更新: {datetime.now().strftime('%H:%M')}")

# 抓取函數
def fetch_data(race_no):
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        if r.status_code != 200: return pd.DataFrame()
        
        soup = BeautifulSoup(r.text, "html.parser")
        rows = []
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 3:
                try:
                    no = tds[0].get_text(strip=True)
                    name = tds[1].get_text(strip=True)
                    odds = tds[2].get_text(strip=True)
                    if no.isdigit() and "SCR" not in odds and odds:
                        rows.append({
                            "RaceID": race_no,
                            "HorseNo": int(no),
                            "HorseName": name,
                            "Odds": float(odds)
                        })
                except: continue
        return pd.DataFrame(rows)
    except: return pd.DataFrame()

# 主程式
if st.button("刷新"): st.rerun()

all_data = []
status = st.empty()

with st.spinner("讀取中..."):
    for i in range(1, total_races + 1):
        status.text(f"讀取第 {i} 場")
        df = fetch_data(i)
        if not df.empty: all_data.append(df)

status.empty()

if len(all_data) > 0:
    df_all = pd.concat(all_data, ignore_index=True)
    st.success(f"成功！共 {len(df_all)} 匹馬")
    
    st.divider()
    col1, col2 = st.columns(2)
    mult = col1.slider("變動幅度(%)", 0, 50, 15)
    thresh = col2.slider("門檻(%)", 0, 30, 5)
    
    df_all["Last"] = df_all["Odds"]
    df_all["First"] = (df_all["Odds"] * (1 + mult/100)).round(1)
    df_all["Drop"] = ((df_all["First"] - df_all["Last"]) / df_all["First"] * 100).round(1)
    
    def signal(row):
        if row["Last"] <= 10 and row["Drop"] > thresh:
            return "🔥" if row["First"] > 10 else "✅"
        return ""
        
    df_all["Sig"] = df_all.apply(signal, axis=1)
    res = df_all[df_all["Sig"] != ""]
    
    if not res.empty:
        st.dataframe(res, use_container_width=True)
    else:
        st.info("無落飛馬")
else:
    st.warning("無數據")



