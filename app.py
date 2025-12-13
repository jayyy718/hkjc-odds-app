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

def fetch_win_place_json(race_date: str, venue: str, start_race: int, end_race: int) -> pd.DataFrame:
    """
    用馬會 JSON 介面抓某日某場次範圍的 Win/Place 賠率
    介面格式大致為：
    https://bet.hkjc.com/racing/getJSON.aspx?type=winplaodds&date=YYYY-MM-DD&venue=ST&start=1&end=10
    回傳欄位：RaceID, HorseNo, HorseName, Odds_Current
    """
    url = (
        "https://bet.hkjc.com/racing/getJSON.aspx"
        f"?type=winplaodds&date={race_date}&venue={venue}"
        f"&start={start_race}&end={end_race}"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Referer": "https://bet.hkjc.com/",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    text = resp.text.strip()

    # 有機會不是標準 JSON，需要檢查一下
    try:
        raw_json = json.loads(text)
    except json.JSONDecodeError as e:
        st.error("無法解析馬會 JSON，請稍後再試或檢查網址 / 參數是否正確。")
        st.code(text[:500])
        raise e

    # Debug: 如第一次使用，可以先打開下面這行睇實際 JSON 結構，再微調下面 parsing。
    # st.write("原始 JSON：", raw_json)

    # 以下為一個常見結構示例：
    # OUT -> WINPLAODDS -> MEETING (list) -> RACE (list) -> HORSE (list)
    odds_root = raw_json.get("OUT", {}).get("WINPLAODDS", {})
    meetings = odds_root.get("MEETING", [])

    rows = []

    for meet in meetings:
        races = meet.get("RACE", [])
        for r in races:
            race_no_str = r.get("NO") or r.get("RACENO")
            try:
                race_no = int(race_no_str)
            except (TypeError, ValueError):
                continue

            horses = r.get("HORSE", [])
            for h in horses:
                horse_no = h.get("NO") or h.get("HNO")
                horse_name = h.get("NAME_C") or h.get("NAME_E") or h.get("NAM")  # 視實際 key 而定
                win_odds_str = h.get("WIN_ODDS") or h.get("WINODDS")

                if not horse_no or not horse_name or not win_odds_str:
                    continue

                if win_odds_str in ["-", "0", "0.0", ""]:
                    continue

                try:
                    win_odds = float(win_odds_str)
                except ValueError:
                    continue

                rows.append(
                    {
                        "RaceID": race_no,
                        "HorseNo": horse_no,
                        "HorseName": horse_name,
                        "Odds_Current": win_odds,
                    }
                )

    return pd.DataFrame(rows)

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
