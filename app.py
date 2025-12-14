import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC 落飛分析 (51saima源)", layout="wide")

st.title("🏇 HKJC 落飛分析 (數據源：51saima)")
st.caption("每 5 分鐘自動從 51saima.com 更新賠率，繞過馬會封鎖。")

# 自動刷新：每 5 分鐘 (300000 ms)
count = st_autorefresh(interval=300000, limit=None, key="auto-refresh")

# ===================== 側邊欄設定 =====================
st.sidebar.header("⚙️ 設定")
total_races = st.sidebar.number_input("今日總場數", 1, 14, 10)
st.sidebar.write(f"最後更新: {datetime.now().strftime('%H:%M:%S')}")

# ===================== 抓取函數 (針對 51saima) =====================

def fetch_odds_from_51saima(race_no):
    """
    從 51saima.com 抓取指定場次的賠率
    URL pattern: https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}
    """
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    
    # 模擬普通瀏覽器
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8' # 確保中文不亂碼
        
        if resp.status_code != 200:
            return pd.DataFrame()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 51saima 的表格結構通常在一個 table 裡
        # 我們找包含賠率數據的行
        rows = []
        
        # 尋找所有表格行 tr
        # 注意：這個網站的 HTML 結構可能比較舊式，我們需要寬鬆地解析
        tables = soup.find_all("table")
        
        for table in tables:
            trs = table.find_all("tr")
            for tr in trs:
                tds = tr.find_all("td")
                
                # 有效的賠率行通常至少有 3-4 個格子 (馬號, 馬名, 賠率...)
                # 且第一個格子是數字 (馬號)
                if len(tds) >= 3:
                    try:
                        no_txt = tds[0].get_text(strip=True)
                        name_txt = tds[1].get_text(strip=True)
                        odds_txt = tds[2].get_text(strip=True)
                        
                        # 簡單驗證：馬號必須是數字
                        if not no_txt.isdigit():
                            continue
                            
                        # 賠率處理：有時會有 "SCR" 或空值
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

    except Exception as e:
        # st.error(f"Race {race_no} 抓取錯誤: {e}")
        return pd.DataFrame()

# ===================== 主邏輯 =====================

st.divider()

if st.button("🔄 立即手動刷新 (或等待自動刷新)"):
    st.rerun()

# 儲存所有場次的數據
all_races_data = []

# 建立一個進度條
progress_bar = st.progress(0)
status_text = st.empty()

with st.spinner("正在從 51saima 抓取全日賠率..."):
    for r in range(1, total_races + 1):
        status_text.text(f"正在抓取第 {r} 場...")
        df_race = fetch_odds_from_51saima(r)
        
        if not df_race.empty:
            all_races_data.append(df_race)
        
        # 更新進度條
        progress_bar.progress(r / total_races)

status_text.text("抓取完成！")
progress_bar.empty()

if all_races_
    df_all = pd.concat(all_races_data, ignore_index=True)
    st.success(f"成功更新！共抓取 {len(df_all)} 匹馬的賠率。")
    
    # 顯示原始數據 (可選，除錯用)
    # st.dataframe(df_all)
    
    # ===================== 落飛分析展示 =====================
    st.divider()
    st.subheader("📊 即時落飛分析")
    
    col1, col2 = st.columns(2)
    with col1:
        odds_multiplier = st.slider("模擬冷熱變動幅度 (%)", 0, 50, 15)
    with col2:
        drop_thresh = st.slider("落飛門檻 (%)", 0, 30, 5)
        
    df_ana = df_all.copy()
    
    # 模擬 5 分鐘前賠率 (因為是單次抓取快照)
    # 未來您可以把這個 df_all 存到 session_state 裡做真正的時間對比
    df_ana["Odds_Final"] = df_ana["Odds_Current"]
    df_ana["Odds_5min"] = (df_ana["Odds_Current"] * (1 + odds_multiplier/100)).round(1)
    
    df_ana["Drop_Percent"] = ((df_ana["Odds_5min"] - df_ana["Odds_Final"]) / df_ana["Odds_5min"] * 100).round(1)
    
    # 篩選落飛馬
    def get_signal(row):
        if row["Odds_Final"] <= 10.0 and row["Drop_Percent"] > drop_thresh:
            return "🔥 強力落飛" if row["Odds_5min"] > 10.0 else "✅ 一般落飛"
        return ""

    df_ana["Signal"] = df_ana.apply(get_signal, axis=1)
    recos = df_ana[df_ana["Signal"] != ""]
    
    if not recos.empty:
        # 依場次排序顯示
        recos = recos.sort_values(by=["RaceID", "HorseNo"])
        
        st.dataframe(
            recos[["RaceID", "HorseNo", "HorseName", "Odds_Final", "Drop_Percent", "Signal"]]
            .style.format({"Odds_Final": "{:.1f}", "Drop_Percent": "{:.1f}%"}),
            use_container_width=True
        )
    else:
        st.info("暫無符合條件的落飛馬匹。")

else:
    st.warning("未能抓取到任何數據。可能原因：\n1. 網站改版或連線逾時。\n2. 目前時段無賠率數據。")

