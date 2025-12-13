import streamlit as st
import pandas as pd
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC 落飛分析 (手動/自動版)", layout="wide")

st.title("🏇 HKJC 落飛分析 (手動/自動雙模式)")
st.caption("因馬會反爬蟲機制，如自動抓取失敗，請使用「手動貼上」模式。")

# ===================== 側邊欄設定 =====================
st.sidebar.header("⚙️ 設定")

# 選擇模式：自動 vs 手動
mode = st.sidebar.radio("數據來源模式", ["手動貼上 (Manual)", "自動抓取 (Auto)"], index=0)

default_date = "2025-12-14"
race_date = st.sidebar.text_input("賽日 (YYYY-MM-DD)", default_date)
venue = st.sidebar.selectbox("馬場", ["ST", "HV"], index=0)

# ===================== 數據處理函數 =====================

def parse_hkjc_data(raw_text, data_type="json"):
    """通用解析函數，處理 JSON 或 XML"""
    rows = []
    try:
        # 1. 嘗試 JSON 解析
        if data_type == "json":
            # 有時候複製下來的文字前後可能有空白，先 strip
            raw_text = raw_text.strip()
            data = json.loads(raw_text)
            
            # 嘗試解析常見 JSON 結構
            meetings = data.get("OUT", {}).get("WINPLAODDS", {}).get("MEETING", [])
            for meet in meetings:
                for race in meet.get("RACE", []):
                    race_no = int(race.get("NO"))
                    for horse in race.get("HORSE", []):
                        try:
                            rows.append({
                                "RaceID": race_no,
                                "HorseNo": horse.get("NO"),
                                "HorseName": horse.get("NAME_C") or horse.get("NAME_E"),
                                "Odds_Current": float(horse.get("WIN_ODDS"))
                            })
                        except: continue
                        
        # 2. 嘗試 XML 解析
        elif data_type == "xml":
            root = ET.fromstring(raw_text)
            for race in root.findall(".//RACE"):
                race_no = int(race.get("NO"))
                for horse in race.findall("HORSE"):
                    try:
                        rows.append({
                            "RaceID": race_no,
                            "HorseNo": horse.get("NO"),
                            "HorseName": horse.get("NAME_C"),
                            "Odds_Current": float(horse.get("WIN_ODDS"))
                        })
                    except: continue
                    
        return pd.DataFrame(rows)
    except Exception as e:
        # 解析失敗時不報錯，回傳空 DataFrame 讓主程式處理
        return pd.DataFrame()

# ===================== 主邏輯 =====================

df_now = pd.DataFrame()

if mode == "手動貼上 (Manual)":
    st.info("💡 操作教學：\n1. 點擊下方連結打開馬會 JSON 頁面。\n2. 等待頁面載入文字 (看起來像亂碼)。\n3. *全選 (Ctrl+A)* 並 *複製 (Ctrl+C)* 頁面所有內容。\n4. 回到這裡，在下方輸入框 *貼上 (Ctrl+V)*。")
    
    # 動態生成連結
    json_link = f"https://bet.hkjc.com/racing/getJSON.aspx?type=winplaodds&date={race_date}&venue={venue}&start=1&end=14"
    st.markdown(f"👉 *[點我打開馬會 JSON 數據]({json_link})* (新分頁開啟)")
    
    raw_input = st.text_area("在此貼上數據內容:", height=200, help="請直接貼上從上述連結複製的全部文字")
    
    if raw_input:
        # 先試 JSON
        df_now = parse_hkjc_data(raw_input, "json")
        if df_now.empty:
            # 再試 XML (有些瀏覽器會自動轉 XML 顯示)
            df_now = parse_hkjc_data(raw_input, "xml")
            
        if not df_now.empty:
            st.success(f"✅ 成功解析 {len(df_now)} 筆數據！")
        else:
            st.error("❌ 無法解析內容。請確認您是否複製了完整的 JSON 文字 (需包含 { 開頭和 } 結尾)。")

elif mode == "自動抓取 (Auto)":
    if st.button("🔄 嘗試自動抓取"):
        with st.spinner("嘗試連線至馬會 (XML 接口)..."):
            try:
                # 嘗試用 XML 接口繞過 JSON 封鎖
                url = f"https://bet.hkjc.com/racing/getXML.aspx?type=winplaodds&date={race_date}&venue={venue}&start=1&end=14"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://bet.hkjc.com/"
                }
                resp = requests.get(url, headers=headers, timeout=10)
                df_now = parse_hkjc_data(resp.text, "xml")
                
                if df_now.empty:
                    st.error("自動抓取失敗 (IP 可能被封鎖)。請切換至「手動貼上」模式。")
                else:
                    st.success(f"成功抓取 {len(df_now)} 筆數據！")
            except Exception as e:
                st.error(f"連線錯誤: {e}")

# ===================== 落飛分析展示 =====================

if not df_now.empty:
    st.divider()
    st.subheader("📊 落飛分析結果")
    
    # 參數設定
    col1, col2 = st.columns(2)
    with col1:
        odds_multiplier = st.slider("模擬冷熱變動幅度 (%)", 0, 50, 15, help="假設 5 分鐘前賠率比現在高多少百分比")
    with col2:
        drop_thresh = st.slider("落飛門檻 (%)", 0, 30, 5, help="跌幅超過此值才視為落飛")
    
    df_ana = df_now.copy()
    # 這裡簡單模擬：假設現價是最終價，模擬一個較高的初始價
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
        st.dataframe(
            recos[["RaceID", "HorseNo", "HorseName", "Odds_Final", "Drop_Percent", "Signal"]]
            .style.format({"Odds_Final": "{:.1f}", "Drop_Percent": "{:.1f}%"}),
            use_container_width=True
        )
    else:
        st.info("暫無符合條件的落飛馬匹。")
