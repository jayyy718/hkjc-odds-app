import streamlit as st
import pandas as pd
import re
import json
import os
import requests
import random
import time
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# ===================== 0. 全局配置 =====================
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

# 偽裝 Headers (模擬瀏覽器)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/",
    "Content-Type": "application/json"
}

@st.cache_resource
def get_static_resources():
    return (
        re.compile(r'^\d+$'),
        re.compile(r'\d+\.?\d*'),
        re.compile(r'[\u4e00-\u9fa5]+')
    )

REGEX_INT, REGEX_FLOAT, REGEX_CHN = get_static_resources()

@st.cache_resource
def get_global_data():
    data = {}
    for i in range(1, 15):
        data[i] = {
            "current_df": pd.DataFrame(),
            "last_df": pd.DataFrame(),
            "last_update": "無數據",
            "raw_odds_text": "",
            "raw_info_text": ""
        }
    return data

race_storage = get_global_data()

# 能力值字典
JOCKEY_RANK = { 'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'C Williams': 5.9, '韋紀力': 5.9, 'R Moore': 5.9, '莫雅': 5.9, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'R Kingscote': 3.8, '金美琪': 3.8, 'A Atzeni': 3.7, '艾兆禮': 3.7, 'B Avdulla': 3.7, '艾道拿': 3.7, 'P N Wong': 3.4, '黃寶妮': 3.4, 'T Marquand': 3.3, '馬昆': 3.3, 'H Doyle': 3.3, '杜苑欣': 3.3, 'E C W Wong': 3.2, '黃智弘': 3.2, 'K C Leung': 3.2, '梁家俊': 3.2, 'B Shinn': 3.0, '薛恩': 3.0, 'K Teetan': 2.8, '田泰安': 2.8, 'H Bentley': 2.7, '班德禮': 2.7, 'M F Poon': 2.6, '潘明輝': 2.6, 'C L Chau': 2.4, '周俊樂': 2.4, 'M Chadwick': 2.4, '蔡明紹': 2.4, 'A Badel': 2.4, '巴度': 2.4, 'L Hewitson': 2.3, '希威森': 2.3, 'J Orman': 2.2, '奧文': 2.2, 'K De Melo': 1.9, '董明朗': 1.9, 'M L Yeung': 1.8, '楊明綸': 1.8, 'Y L Chung': 1.8, '鍾易禮': 1.8, 'A Hamelin': 1.7, '賀銘年': 1.7, 'H T Mo': 1.3, '巫顯東': 1.3, 'B Thompson': 0.9, '湯普新': 0.9, 'A Pouchin': 0.8, '普珍宜': 0.8 }
TRAINER_RANK = { 'J Size': 4.4, '蔡約翰': 4.4, 'K L Man': 4.3, '文家良': 4.3, 'K W Lui': 4.0, '呂健威': 4.0, 'D Eustace': 3.9, '游達榮': 3.9, 'C Fownes': 3.9, '方嘉柏': 3.9, 'P F Yiu': 3.7, '姚本輝': 3.7, 'D A Hayes': 3.7, '大衛希斯': 3.7, 'M Newnham': 3.6, '廖康銘': 3.6, 'W Y So': 3.4, '蘇偉賢': 3.4, 'W K Mo': 3.3, '巫偉傑': 3.3, 'F C Lor': 3.2, '羅富全': 3.2, 'C H Yip': 3.2, '葉楚航': 3.2, 'C S Shum': 3.1, '沈集成': 3.1, 'K H Ting': 3.1, '丁冠豪': 3.1, 'A S Cruz': 3.0, '告東尼': 3.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'Y S Tsui': 2.5, '徐雨石': 2.5, 'J Richards': 2.3, '黎昭昇': 2.3, 'D J Hall': 2.3, '賀賢': 2.3, 'C W Chang': 2.2, '鄭俊偉': 2.2, 'T P Yung': 2.1, '容天鵬': 2.1 }

# ===================== 1. HKJC API 整合 (核心部分) =====================
def fetch_hkjc_data(race_no):
    """
    透過 HKJC JSON 接口獲取即時賠率 (參考 GitHub 開源項目邏輯)
    """
    try:
        today_str = datetime.now(HKT).strftime("%Y-%m-%d")
        
        url = "https://bet.hkjc.com/racing/getJSON.aspx"
        params = {
            "type": "winodds",
            "date": today_str,
            "venue": "ST", # 默認沙田
            "start": race_no,
            "end": race_no
        }
        
        # 嘗試請求沙田 (ST)
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        
        # 如果 ST 沒數據，嘗試跑馬地 (HV)
        if resp.status_code != 200 or "OUT" not in resp.text:
            params["venue"] = "HV"
            resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
            
        if resp.status_code == 200:
            try:
                data = resp.json()
            except:
                return None, "API 回傳格式錯誤 (非 JSON)"

            if "OUT" in 
                raw_str = data["OUT"]
                if ";" in raw_str:
                    parts = raw_str.split(";")
                    odds_map = {}
                    for p in parts:
                        if "=" in p:
                            k, v = p.split("=")
                            if k.isdigit():
                                try:
                                    val = float(v)
                                    odds_map[int(k)] = val if val < 900 else 0.0
                                except:
                                    pass
                    
                    if odds_map:
                        # 創建 DataFrame
                        df = pd.DataFrame(list(odds_map.items()), columns=["馬號", "現價"])
                        # 添加臨時馬名
                        df["馬名"] = df["馬號"].apply(lambda x: f"馬匹 {x}") 
                        return df, None
            
            return None, "找不到該場次賠率數據 (可能未開售或日期錯誤)"
            
        else:
            return None, f"連線錯誤: {resp.status_code}"
            
    except Exception as e:
        return None, f"API 錯誤: {str(e)}"

# ===================== 2. 輔助函數 =====================

def save_daily_history(data_dict):
    history_data = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: history_data = json.load(f)
            except: history_data = {}
    
    today_str = datetime.now(HKT).strftime("%Y-%m-%d")
    daily_export = {}
    for race_id, race_content in data_dict.items():
        if not race_content["current_df"].empty:
            daily_export[str(race_id)] = {
                "odds_data": race_content["current_df"].to_dict(orient="records"),
                "raw_odds": race_content["raw_odds_text"],
                "raw_info": race_content["raw_info_text"],
                "update_time": race_content["last_update"]
            }
    if daily_export:
        history_data[today_str] = daily_export
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, ensure_ascii=False, indent=4)
        return True, today_str
    return False, "無數據"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except: return {}
    return {}

def get_ability_score(name, rank_dict):
    for key in rank_dict:
        if key in name or name in key: return rank_dict[key]
    return 2.0

def parse_info_data(text):
    rows = []
    lines = text.strip().split('\n')
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 8 and parts[0].isdigit():
            try:
                no = int(parts[0])
                chn_words = [p for p in parts if REGEX_CHN.match(p)]
                if len(chn_words) >= 3:
                    rows.append({"馬號": no, "騎師": chn_words[1], "練馬師": chn_words[2]})
            except: continue
    if rows: return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

def calculate_score(row):
    s = 0
    trend = row.get("真實走勢(%)", 0)
    if trend >= 15: s += 50
    elif trend >= 10: s += 35
    elif trend >= 5: s += 20
    elif trend <= -10: s -= 20
    
    odds = row.get("現價", 999)
    if odds <= 5.0: s += 25
    elif odds <= 10.0: s += 10
    
    j = get_ability_score(row.get("騎師", ""), JOCKEY_RANK)
    t = get_ability_score(row.get("練馬師", ""), TRAINER_RANK)
    s += j * 2.5
    s += t * 1.5
    return round(s, 1)

def get_level(score):
    if score >= 80: return "A"
    elif score >= 70: return "B"
    elif score >= 60: return "C"
    else: return "-"

# ===================== 3. 頁面配置 =====================
st.set_page_config(page_title="HKJC 賽馬智腦 (API版)", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f5f7f9; color: #000000 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #ddd; }
    div[data-testid="stExpander"] { background-color: #ffffff !important; border: 1px solid #cccccc !important; border-radius: 8px !important; color: #000000 !important; }
    .main-title { color: #1a237e; font-weight: 800; font-size: 28px; letter-spacing: 1px; }
    .horse-card { background-color: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd; border-top: 4px solid #1a237e; margin-bottom: 8px; }
    .top-pick-card { border-top: 4px solid #c62828; }
    .status-tag { display: inline-block; padding: 2px 6px; border-radius: 2px; font-size: 11px; font-weight: bold; }
    .tag-drop { background-color: #ffebee; color: #c62828; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32; } 
    .tag-top { background-color: #1a237e; color: white; }    
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="border-bottom: 2px solid #1a237e; padding-bottom: 5px; margin-bottom: 10px;">
    <span class="main-title">賽馬智腦</span>
    <span style="font-size:14px; color:#fff; background-color:#1a237e; padding:3px 8px; border-radius:4px; margin-left:8px; vertical-align:middle;">API Enhanced</span>
</div>
""", unsafe_allow_html=True)

# ===================== 4. Sidebar =====================
with st.sidebar:
    st.markdown("### 模式 Mode")
    app_mode = st.radio("功能", ["📡 實時 (Live)", "📜 歷史 (History)", "📈 今日總覽"], label_visibility="collapsed")
    st.divider()
    st.markdown("### API 設定")
    venue_select = st.selectbox("賽事場地", ["ST (沙田)", "HV (跑馬地)"], index=0)
    st.divider()
    top_pick_threshold = st.slider("TOP PICKS 門檻", 50, 85, 65, 1)

    if app_mode == "📡 實時 (Live)":
        st.divider()
        st.markdown("### 賽事導航")
        selected_race = st.selectbox("選擇場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        st_autorefresh(interval=30000, key="live_refresh") 

    # 管理員按鈕
    st.divider()
    if st.button("💾 封存今日數據", help="將今日所有數據寫入歷史檔案"):
        success, msg = save_daily_history(race_storage)
        if success: st.success("已封存！")
        else: st.warning(msg)

# ============= Live 模式 =============
if app_mode == "📡 實時 (Live)":
    current_race = race_storage[selected_race]

    # API 控制按鈕
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 立即更新賠率", type="primary", use_container_width=True):
            with st.spinner("正在連接 HKJC 伺服器..."):
                df_api, err = fetch_hkjc_data(selected_race)
                if df_api is not None:
                    # 保留排位資料
                    if not current_race["current_df"].empty:
                        old_info = current_race["current_df"][["馬號", "馬名", "騎師", "練馬師"]]
                        # 合併：保留舊的馬名，除非它是 "馬匹 N"
                        df_api = df_api.drop(columns=["馬名"], errors="ignore").merge(old_info, on="馬號", how="left")
                        # 填充空缺
                        if "馬名" not in df_api.columns: df_api["馬名"] = df_api["馬號"].apply(lambda x: f"馬匹 {x}")
                        else: df_api["馬名"] = df_api["馬名"].fillna(df_api["馬號"].apply(lambda x: f"馬匹 {x}"))
                    
                    # 歷史記錄更新
                    if not current_race["current_df"].empty:
                        current_race["last_df"] = current_race["current_df"]
                    else:
                        current_race["last_df"] = df_api
                    
                    current_race["current_df"] = df_api
                    current_race["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                    st.success("數據已更新！")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(err)
    
    with c2:
        st.info(f"上次更新: {current_race['last_update']} | 場地: {venue_select[:2]}")

    # 手動輸入備用
    with st.expander("🛠️ 手動輸入 / 修正排位資料"):
        with st.form(key=f"manual_form_{selected_race}"):
            st.caption("在此貼上排位表文字 (包含馬名、騎師、練馬師)，API 會自動合併賠率。")
            new_info = st.text_area("排位數據", value=current_race["raw_info_text"], height=100)
            if st.form_submit_button("更新排位資料"):
                if new_info:
                    df_info = parse_info_data(new_info)
                    if not df_info.empty:
                        if not current_race["current_df"].empty:
                            df_curr = current_race["current_df"]
                            # 移除舊列
                            cols = [c for c in ["騎師", "練馬師", "馬名"] if c in df_curr.columns]
                            df_curr = df_curr.drop(columns=cols, errors='ignore')
                            # 合併新資料
                            # 注意：parse_info_data 目前只抓騎練，我們可以修改它也嘗試抓馬名，
                            # 但目前邏輯是合併騎練。如果排位表裡有馬名，可以進一步優化解析邏輯。
                            df_merged = df_curr.merge(df_info, on="馬號", how="left")
                            df_merged["騎師"] = df_merged["騎師"].fillna("未知")
                            df_merged["練馬師"] = df_merged["練馬師"].fillna("未知")
                            current_race["current_df"] = df_merged
                            current_race["raw_info_text"] = new_info
                            st.success("排位資料已更新！")
                            st.rerun()
                        else:
                            st.warning("請先按「立即更新賠率」獲取基礎馬號列表，再更新排位資料。")

    if not current_race["current_df"].empty:
        df = current_race["current_df"].copy()
        last = current_race["last_df"].copy()
        
        # 填充
        for c in ["騎師", "練馬師"]:
            if c not in df.columns: df[c] = "未知"
            
        last_odds = last[["馬號", "現價"]].rename(columns={"現價": "上回"})
        if "上回" not in df.columns:
            df = df.merge(last_odds, on="馬號", how="left")
            df["上回"] = df["上回"].fillna(df["現價"])
            
        df["真實走勢(%)"] = ((df["上回"] - df["現價"]) / df["上回"] * 100).fillna(0).round(1)
        df["得分"] = df.apply(calculate_score, axis=1)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        df["信心級別"] = df["得分"].apply(get_level)
        
        tab1, tab2 = st.tabs(["📋 總覽", "📑 明細"])
        with tab1:
            max_horse = df.iloc[0]
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("最高評分", f"#{max_horse['馬號']} ({max_horse['得分']})", f"{max_horse['現價']}")
            with c2: st.metric("平均分", f"{df['得分'].mean().round(1)}")
            with c3: st.metric("落飛馬匹", int((df["真實走勢(%)"] > 0).sum()))
            
            top_picks = df[df["得分"] >= top_pick_threshold]
            if not top_picks.empty:
                st.markdown(f"**🔥 重點推薦 (>{top_pick_threshold})**")
                cols = st.columns(min(len(top_picks), 3))
                for idx, col in enumerate(cols):
                    if idx < len(top_picks):
                        row = top_picks.iloc[idx]
                        t_val = row["真實走勢(%)"]
                        trend_html = (f"<span class='status-tag tag-drop'>落飛 {abs(t_val)}%</span>" if t_val > 0 
                                      else f"<span class='status-tag tag-rise'>回飛 {abs(t_val)}%</span>" if t_val < 0 
                                      else "<span style='color:#999'>-</span>")
                        with col:
                            st.markdown(f"""
                            <div class="horse-card top-pick-card">
                                <div style="display:flex; justify-content:space-between;">
                                    <strong>#{row['馬號']} {row['馬名']}</strong>
                                    <span class="status-tag tag-top">{row['信心級別']}級</span>
                                </div>
                                <div style="display:flex; justify-content:space-between; margin-top:5px;">
                                    <span style="font-size:18px; font-weight:bold;">{row['現價']}</span>
                                    <span style="color:#c62828; font-weight:bold; font-size:18px;">{row['得分']}</span>
                                </div>
                                <div style="margin-top:5px; font-size:12px;">{trend_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("暫無推薦")
                
        with tab2:
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("⚠️ 暫無數據，請按上方的「🔄 立即更新賠率」按鈕。")

elif app_mode == "📜 歷史 (History)":
    st.markdown("#### 📜 歷史回顧")
    history_db = load_history()
    if history_db:
        d_list = sorted(history_db.keys(), reverse=True)
        sel_date = st.selectbox("日期", d_list)
        if sel_date:
            sel_race = st.selectbox("場次", sorted([int(k) for k in history_db[sel_date].keys()]), format_func=lambda x: f"第 {x} 場")
            if sel_race:
                data = history_db[sel_date][str(sel_race)]
                df_h = pd.DataFrame(data["odds_data"])
                if "真實走勢(%)" not in df_h.columns: df_h["真實走勢(%)"] = 0.0
                df_h["得分"] = df_h.apply(calculate_score, axis=1)
                df_h = df_h.sort_values(["得分", "現價"], ascending=[False, True])
                st.dataframe(df_h, use_container_width=True, hide_index=True)
    else:
        st.info("無歷史數據")

elif app_mode == "📈 今日總覽":
    st.markdown("#### 📈 今日總覽")
    history_db = load_history()
    today_str = datetime.now(HKT).strftime("%Y-%m-%d")
    if today_str in history_db:
        daily = history_db[today_str]
        rows = []
        for rid in sorted([int(k) for k in daily.keys()]):
            d = daily[str(rid)]
            df = pd.DataFrame(d["odds_data"])
            if not df.empty:
                df["得分"] = df.apply(calculate_score, axis=1)
                top = df.sort_values("得分", ascending=False).iloc[0]
                rows.append({"場次": rid, "推薦": f"#{top['馬號']} {top.get('馬名','')} ({top['得分']})"})
        st.table(pd.DataFrame(rows))
    else:
        st.info("今日尚未封存數據")
