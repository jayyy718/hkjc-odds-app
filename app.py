import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
import json
from datetime import datetime

# ===================== 頁面與自動刷新設定 =====================
st.set_page_config(page_title="HKJC 即時賠率落飛分析", layout="wide")

st.title("🏇 HKJC 即時賠率落飛分析（實數據 JSON 版）")
st.caption("資料來源：香港賽馬會 eWin Win/Place JSON 介面（僅供數據研究用途）")

# 每 5 分鐘自動 rerun 一次（300000 ms）
refresh_count = st_autorefresh(interval=300000, limit=None, key="hkjc-auto-refresh")

# ===================== 側邊欄：賽日 / 場地設定 =====================
st.sidebar.header("📅 賽事設定")

default_date = "2025-12-14"  # 你可以按實際賽日修改
race_date = st.sidebar.text_input("賽日 (YYYY-MM-DD)", default_date)

racecourse_label = st.sidebar.selectbox(
    "馬場",
    options=["沙田 (ST)", "跑馬地 (HV)"],
    index=0
)
venue = "ST" if "ST" in racecourse_label else "HV"

total_races = st.sidebar.number_input("全日場數", min_value=1, max_value=12, value=10, step=1)

st.sidebar.markdown("---")
st.sidebar.write(f"🔁 自動刷新次數：{refresh_count}")
st.sidebar.write(f"⏱️ 現在時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===================== 抓取 JSON 賠率函數 =====================

import xml.etree.ElementTree as ET

def fetch_win_place_json(race_date: str, venue: str, start_race: int, end_race: int) -> pd.DataFrame:
    """
    【修復版】改用 XML 接口抓取賠率，以繞過 JSON 接口的封鎖
    URL: https://bet.hkjc.com/racing/getXML.aspx?type=winplaodds&date=...
    """
    
    # 改用 getXML.aspx 接口
    url = (
        "https://bet.hkjc.com/racing/getXML.aspx"
        f"?type=winplaodds&date={race_date}&venue={venue}"
        f"&start={start_race}&end={end_race}"
    )

    # 模擬真實瀏覽器的 Headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://bet.hkjc.com/racing/pages/odds_wp.aspx?lang=ch",
        "Accept": "application/xml, text/xml, /",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        
        # 解析 XML
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            # 如果 XML 解析失敗，可能是真的被完全封鎖，或者是編碼問題
            st.error("無法解析馬會數據 (XML 格式錯誤)。可能今日無賽事或 IP 被封鎖。")
            return pd.DataFrame()

        rows = []
        
        # XML 結構通常是: <WINPLAODDS><MEETING><RACE><HORSE>...</HORSE></RACE></MEETING></WINPLAODDS>
        # 我們直接找所有的 "HORSE" 標籤
        for race in root.findall(".//RACE"):
            try:
                race_no = int(race.get("NO"))
            except:
                continue
                
            for horse in race.findall("HORSE"):
                try:
                    horse_no = horse.get("NO")
                    horse_name = horse.get("NAME_C") # 中文名
                    win_odds_str = horse.get("WIN_ODDS")
                    
                    if not win_odds_str or win_odds_str in ["-", "0", "0.0", ""]:
                        continue
                        
                    win_odds = float(win_odds_str)
                    
                    rows.append({
                        "RaceID": race_no,
                        "HorseNo": horse_no,
                        "HorseName": horse_name,
                        "Odds_Current": win_odds
                    })
                except:
                    continue

        return pd.DataFrame(rows)

    except Exception as e:
        st.error(f"連線錯誤 (XML): {e}")
        return pd.DataFrame()

# ===================== 主流程：抓實時賠率 =====================

st.divider()
st.subheader("📡 即時 Win 賠率（JSON 抓取）")

with st.spinner("正在從馬會 JSON 介面讀取賠率數據..."):
    try:
        df_now = fetch_win_place_json(
            race_date=race_date,
            venue=venue,
            start_race=1,
            end_race=total_races,
        )
    except Exception as e:
        st.error(f"抓取賠率時出錯：{e}")
        df_now = pd.DataFrame()

if df_now.empty:
    st.error(
        "未能讀取到任何賠率資料，可能原因：\n"
        "- 今日 / 指定日期未有賽事\n"
        "- JSON 結構有變，需要微調程式解析部份\n"
        "- 被暫時限流，稍後再試"
    )
    st.stop()

st.success(f"✅ 成功讀取 {len(df_now)} 筆馬匹即時賠率數據。")

st.dataframe(df_now.sort_values(["RaceID", "HorseNo"]), use_container_width=True)

# ===================== 落飛分析（以單次快照作 Demo） =====================

st.divider()
st.subheader("🎯 單次快照落飛信號 Demo")

st.markdown(
    "因為目前只抓到「這一刻」的賠率，"
    "要模擬你嘅『5 分鐘前賠率 vs 現在賠率』，"
    "暫時用一個簡單模型：假設 5 分鐘前賠率比現在高一點點。"
)

# 模擬 5 分鐘前賠率比現在高 X%
odds_up_percent = st.slider("模擬 5 分鐘前賠率比現價高 (%)", 0, 50, 15, step=5)

df_demo = df_now.copy()
df_demo["Odds_Final"] = df_demo["Odds_Current"]
df_demo["Odds_5min"] = (df_demo["Odds_Current"] * (1 + odds_up_percent / 100)).round(1)

df_demo["Drop_Percent"] = (
    (df_demo["Odds_5min"] - df_demo["Odds_Final"]) / df_demo["Odds_5min"] * 100
).round(1)

drop_threshold = st.slider("判定為落飛的跌幅門檻 (%)", 0.0, 30.0, 5.0, step=1)

def classify_signal(row):
    """
    根據你之前設計邏輯：
    - 最終賠率 <= 10 倍，且跌幅 > 門檻 => 落飛
      - 如果由 10 倍以上跌落來 => 強力落飛 (冷變熱)
      - 否則 => 一般落飛 (熱更熱)
    - 由 10 倍以下升上 10 倍以上 => 回飛 (被放棄)
    """
    if row["Odds_Final"] <= 10.0 and row["Drop_Percent"] > drop_threshold:
        if row["Odds_5min"] > 10.0:
            return "🔥 強力落飛 (冷變熱)"
        else:
            return "✅ 一般落飛 (熱更熱)"
    elif row["Odds_Final"] > 10.0 and row["Odds_5min"] <= 10.0:
        return "❌ 回飛 (被放棄)"
    else:
        return "➖ 無顯著變化"

df_demo["Signal"] = df_demo.apply(classify_signal, axis=1)

reco = df_demo[df_demo["Signal"].str.contains("落飛")].copy()

c1, c2, c3 = st.columns(3)
c1.metric("目前有賠率的馬匹數", len(df_demo))
c2.metric("落飛信號馬匹數", len(reco))
c3.metric("最後更新時間", datetime.now().strftime("%H:%M:%S"))

st.markdown("#### 📋 落飛馬匹列表")
if reco.empty:
    st.info("暫時沒有符合門檻的落飛信號馬匹。")
else:
    show_cols = ["RaceID", "HorseNo", "HorseName", "Odds_5min", "Odds_Final", "Drop_Percent", "Signal"]
    st.dataframe(
        reco.sort_values(["RaceID", "HorseNo"])[show_cols]
        .style.format({"Odds_5min": "{:.1f}", "Odds_Final": "{:.1f}", "Drop_Percent": "{:.1f}%"}),
        use_container_width=True
    )

st.markdown("#### 📈 各匹馬現價賠率分佈")
chart_df = df_demo[["HorseName", "Odds_Final"]].set_index("HorseName")
st.bar_chart(chart_df)

st.markdown("---")
st.caption("⚠️ 本工具僅供數據研究與教育用途，並不構成任何投注建議。博彩有風險，請量力而為。")
