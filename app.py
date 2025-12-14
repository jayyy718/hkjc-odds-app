import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC落飛分析", layout="wide")

st.title("🏇 HKJC 落飛分析 (數據源：51saima)")
st.caption("每5分鐘自動更新")

# 自動刷新
count = st_autorefresh(interval=300000, limit=None, key="auto-refresh")

# ===================== 設定 =====================
st.sidebar.header("設定")
total_races = st.sidebar.number_input("今日總場數", 1, 14, 10)
st.sidebar.write(f"更新時間: {datetime.now().strftime('%H:%M:%S')}")

# ===================== 抓取函數 =====================
def fetch_odds_from_51saima(race_no):
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        if resp.status_code != 200:
            return pd.DataFrame()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = []
        tables = soup.find_all("table")
        
        for table in tables:
            trs = table.find_all("tr")
            for tr in trs:
                tds = tr.find_all("td")
                if len(tds) >= 3:
                    try:
                        no_txt = tds[0].get_text(strip=True)
                        name_txt = tds[1].get_text(strip=True)
                        odds_txt = tds[2].get_text(strip=True)
                        
                        if not no_txt.isdigit():
                            continue
                        if "SCR" in odds_txt or odds_txt == "":
                            continue
                            
                        rows.append({
                            "RaceID": race_no,
                            "HorseNo": int(no_txt),
                            "HorseName": name_txt,
                            "Odds_Current": float(odds_txt)
                        })
                    except:
                        continue
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

# ===================== 主邏輯 =====================
st.divider()

if st.button("手動刷新"):
    st.rerun()

all_races_data = []
progress_bar = st.progress(0)
status_text = st.empty()

with st.spinner("讀取中..."):
    for r in range(1, total_races + 1):
        status_text.text(f"讀取第 {r} 場...")
        df_race = fetch_odds_from_51saima(r)
        if not df_race.empty:
            all_races_data.append(df_race)
        progress_bar.progress(r / total_races)

status_text.text("完成")
progress_bar.empty()

if all_races_
    df_all = pd.concat(all_races_data, ignore_index=True)
    st.success(f"成功更新！共 {len(df_all)} 匹馬。")
    
    st.divider()
    st.subheader("分析結果")
    
    col1, col2 = st.columns(2)
    with col1:
        odds_multiplier = st.slider("模擬冷熱變動幅度(%)", 0, 50, 15)
    with col2:
        drop_thresh = st.slider("落飛門檻(%)", 0, 30, 5)
        
    df_ana = df_all.copy()
    df_ana["Odds_Final"] = df_ana["Odds_Current"]
    df_ana["Odds_5min"] = (df_ana["Odds_Current"] * (1 + odds_multiplier/100)).round(1)
    df_ana["Drop_Percent"] = ((df_ana["Odds_5min"] - df_ana["Odds_Final"]) / df_ana["Odds_5min"] * 100).round(1)
    
    # 這裡是最容易出錯的地方，我改得更保險一點
    def get_signal(row):
        is_drop = row["Odds_Final"] <= 10.0 and row["Drop_Percent"] > drop_thresh
        if is_drop:
            if row["Odds_5min"] > 10.0:
                return "強力落飛"
            else:
                return "一般落飛"
        return ""

    df_ana["Signal"] = df_ana.apply(get_signal, axis=1)
    recos = df_ana[df_ana["Signal"] != ""]
    
    if not recos.empty:
        recos = recos.sort_values(by=["RaceID", "HorseNo"])
        st.dataframe(
            recos[["RaceID", "HorseNo", "HorseName", "Odds_Final", "Drop_Percent", "Signal"]]
            .style.format({"Odds_Final": "{:.1f}", "Drop_Percent": "{:.1f}%"}),
            use_container_width=True
        )
    else:
        st.info("無落飛馬匹")
else:
    st.warning("無數據。請稍後再試。")


