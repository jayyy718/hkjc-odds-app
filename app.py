import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time

# ===================== 設定 =====================
st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (穩定版)")
count = st_autorefresh(interval=300000, limit=None, key="auto")

total_races = st.sidebar.number_input("今日場數", 1, 14, 10)
st.sidebar.write(f"更新: {datetime.now().strftime('%H:%M')}")

# ===================== 核心函數 =====================
def fetch_race(race_no):
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.51saima.com/mobi/index.jsp"
    }
    
    # 重試 3 次
    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.encoding = 'utf-8'
            if r.status_code != 200:
                time.sleep(1)
                continue
                
            soup = BeautifulSoup(r.text, "html.parser")
            tds = soup.find_all("td")
            
            if not tds:
                time.sleep(1)
                continue

            rows = []
            i = 0
            while i < len(tds) - 2:
                try:
                    t1 = tds[i].get_text(strip=True)
                    t2 = tds[i+1].get_text(strip=True)
                    t3 = tds[i+2].get_text(strip=True)
                    
                    if t1.isdigit():
                        no = int(t1)
                        if no > 24: # 過濾異常數字
                            i += 1
                            continue
                            
                        # 找賠率數字
                        odds = re.findall(r"\d+\.\d+", t3)
                        if odds:
                            rows.append({
                                "RaceID": race_no,
                                "HorseNo": no,
                                "HorseName": t2,
                                "Odds": float(odds[0])
                            })
                except: pass
                i += 1
            
            if rows:
                df = pd.DataFrame(rows)
                df = df.drop_duplicates(subset=["HorseNo"], keep="last")
                if len(df) >= 5: return df
            time.sleep(1)
        except:
            time.sleep(1)
            
    return pd.DataFrame()

# ===================== 主程序 =====================
if st.button("刷新"): st.rerun()

if 'last_df' not in st.session_state:
    st.session_state.last_df = pd.DataFrame()

temp_list = []
bar = st.progress(0)
txt = st.empty()

with st.spinner("抓取中..."):
    for i in range(1, total_races + 1):
        txt.text(f"讀取第 {i} 場...")
        df = fetch_race(i)
        if not df.empty:
            temp_list.append(df)
        time.sleep(0.3) # 避免太快
        bar.progress(i / total_races)

txt.empty()
bar.empty()

# 這裡就是修正過的地方
if len(temp_list) > 0:
    df_all = pd.concat(temp_list, ignore_index=True)
    st.session_state.last_df = df_all
    st.success(f"成功更新！共 {len(df_all)} 匹馬。")
else:
    if st.session_state.last_df.empty:
        st.error("無法獲取數據，請稍後再試。")
    else:
        st.warning("本次無新數據，顯示舊記錄。")

# 顯示分析
if not st.session_state.last_df.empty:
    df_show = st.session_state.last_df.copy()
    
    st.divider()
    c1, c2 = st.columns(2)
    mult = c1.slider("變動(%)", 0, 50, 15)
    thresh = c2.slider("門檻(%)", 0, 30, 5)
    
    df_show["Last"] = df_show["Odds"]
    df_show["First"] = (df_show["Odds"] * (1 + mult/100)).round(1)
    df_show["Drop"] = ((df_show["First"] - df_show["Last"]) / df_show["First"] * 100).round(1)
    
    def sig(row):
        if row["Last"] <= 10 and row["Drop"] > thresh:
            return "🔥" if row["First"] > 10 else "✅"
        return ""
        
    df_show["Sig"] = df_show.apply(sig, axis=1)
    res = df_show[df_show["Sig"] != ""]
    
    if not res.empty:
        res = res.sort_values(by=["RaceID", "HorseNo"])
        st.dataframe(res, use_container_width=True)
    else:
        st.info("無落飛馬")
