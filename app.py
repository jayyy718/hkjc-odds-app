import streamlit as st
import pandas as pd
import re
import json
import os
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# ===================== 0. 全局配置 (極簡化) =====================
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

# 靜態資源快取
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

# 常數定義
JOCKEY_RANK = { 'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'C Williams': 5.9, '韋紀力': 5.9, 'R Moore': 5.9, '莫雅': 5.9, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'R Kingscote': 3.8, '金美琪': 3.8, 'A Atzeni': 3.7, '艾兆禮': 3.7, 'B Avdulla': 3.7, '艾道拿': 3.7, 'P N Wong': 3.4, '黃寶妮': 3.4, 'T Marquand': 3.3, '馬昆': 3.3, 'H Doyle': 3.3, '杜苑欣': 3.3, 'E C W Wong': 3.2, '黃智弘': 3.2, 'K C Leung': 3.2, '梁家俊': 3.2, 'B Shinn': 3.0, '薛恩': 3.0, 'K Teetan': 2.8, '田泰安': 2.8, 'H Bentley': 2.7, '班德禮': 2.7, 'M F Poon': 2.6, '潘明輝': 2.6, 'C L Chau': 2.4, '周俊樂': 2.4, 'M Chadwick': 2.4, '蔡明紹': 2.4, 'A Badel': 2.4, '巴度': 2.4, 'L Hewitson': 2.3, '希威森': 2.3, 'J Orman': 2.2, '奧文': 2.2, 'K De Melo': 1.9, '董明朗': 1.9, 'M L Yeung': 1.8, '楊明綸': 1.8, 'Y L Chung': 1.8, '鍾易禮': 1.8, 'A Hamelin': 1.7, '賀銘年': 1.7, 'H T Mo': 1.3, '巫顯東': 1.3, 'B Thompson': 0.9, '湯普新': 0.9, 'A Pouchin': 0.8, '普珍宜': 0.8 }
TRAINER_RANK = { 'J Size': 4.4, '蔡約翰': 4.4, 'K L Man': 4.3, '文家良': 4.3, 'K W Lui': 4.0, '呂健威': 4.0, 'D Eustace': 3.9, '游達榮': 3.9, 'C Fownes': 3.9, '方嘉柏': 3.9, 'P F Yiu': 3.7, '姚本輝': 3.7, 'D A Hayes': 3.7, '大衛希斯': 3.7, 'M Newnham': 3.6, '廖康銘': 3.6, 'W Y So': 3.4, '蘇偉賢': 3.4, 'W K Mo': 3.3, '巫偉傑': 3.3, 'F C Lor': 3.2, '羅富全': 3.2, 'C H Yip': 3.2, '葉楚航': 3.2, 'C S Shum': 3.1, '沈集成': 3.1, 'K H Ting': 3.1, '丁冠豪': 3.1, 'A S Cruz': 3.0, '告東尼': 3.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'Y S Tsui': 2.5, '徐雨石': 2.5, 'J Richards': 2.3, '黎昭昇': 2.3, 'D J Hall': 2.3, '賀賢': 2.3, 'C W Chang': 2.2, '鄭俊偉': 2.2, 'T P Yung': 2.1, '容天鵬': 2.1 }

# ===================== 1. 功能函數 (無 IO 操作) =====================

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
            return json.load(f)
    return {}

def get_ability_score(name, rank_dict):
    for key in rank_dict:
        if key in name or name in key: return rank_dict[key]
    return 2.0

def parse_odds_data(text):
    rows = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    i = 0
    L = len(lines)
    while i < L:
        if REGEX_INT.match(lines[i]):
            try:
                no = int(lines[i])
                name = lines[i+1] if i+1 < L else "未知"
                win = 0.0
                if i+2 < L:
                    nums = REGEX_FLOAT.findall(lines[i+2])
                    if nums: win = float(nums[0])
                if win > 0:
                    rows.append({"馬號": no, "馬名": name, "現價": win})
                    i += 3
                    continue
            except: pass
        i += 1
    if rows: return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

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
st.set_page_config(page_title="HKJC 賽馬智腦 By Jay", layout="wide")

# CSS 優化：減少渲染負擔
st.markdown("""
<style>
    .stApp { background-color: #f5f7f9; color: #000000 !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #ddd; }
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
    <span style="font-size:14px; color:#fff; background-color:#1a237e; padding:3px 8px; border-radius:4px; margin-left:8px; vertical-align:middle;">By Jay</span>
</div>
""", unsafe_allow_html=True)

st.markdown("> 極速版：專注即時數據與評分，移除複雜圖表以提升速度。")

# ===================== 4. Sidebar =====================
with st.sidebar:
    st.markdown("### 模式 Mode")
    app_mode = st.radio(
        "功能",
        ["📡 實時 (Live)", "📜 歷史 (History)", "📈 今日總覽"],
        label_visibility="collapsed"
    )
    st.divider()

    st.markdown("### 設定")
    top_pick_threshold = st.slider("TOP PICKS 門檻", 50, 85, 65, 1)

    if app_mode == "📡 實時 (Live)":
        st.divider()
        st.markdown("### 賽事導航")
        selected_race = st.selectbox("選擇場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        
        st.divider()
        st.markdown("### 管理員")
        password = st.text_input("密碼", type="password")
        is_admin = (password == "jay123")
        if is_admin:
            if st.button("💾 封存今日", use_container_width=True):
                success, msg = save_daily_history(race_storage)
                if success: st.success(msg)
                else: st.warning(msg)
        # [手動刷新] 移除自動刷新，改為手動，徹底解決卡頓
        if st.button("🔄 刷新頁面", type="primary", use_container_width=True):
            st.rerun()
    
    elif app_mode == "📜 歷史 (History)":
        st.divider()
        st.markdown("### 檔案 Archive")
        history_db = load_history()
        if history_db:
            selected_date = st.selectbox("日期", sorted(history_db.keys(), reverse=True))
            selected_history_race = st.selectbox("場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        else:
            st.warning("無紀錄")
            selected_date = None

# ============= Live 模式 =============
if app_mode == "📡 實時 (Live)":
    current_race = race_storage[selected_race]

    if 'is_admin' in locals() and is_admin:
        with st.expander(f"⚙️ 數據控制台 (第 {selected_race} 場)", expanded=True):
            with st.form(key=f"form_race_{selected_race}"):
                c1, c2 = st.columns(2)
                with c1: new_odds = st.text_area("賠率", value=current_race["raw_odds_text"], height=100)
                with c2: new_info = st.text_area("排位", value=current_race["raw_info_text"], height=100)
                
                if st.form_submit_button("🚀 發布更新", type="primary", use_container_width=True):
                    df_odds = parse_odds_data(new_odds)
                    if not df_odds.empty:
                        df_info = parse_info_data(new_info) if new_info else pd.DataFrame()
                        if not df_info.empty: df_odds = df_odds.join(df_info, how="left")
                        for col in ["騎師", "練馬師"]:
                            if col not in df_odds.columns: df_odds[col] = "未知"
                            df_odds[col] = df_odds[col].fillna("未知")
                        
                        if not current_race["current_df"].empty: current_race["last_df"] = current_race["current_df"]
                        else: current_race["last_df"] = df_odds
                            
                        current_race["current_df"] = df_odds
                        current_race["raw_odds_text"] = new_odds
                        current_race["raw_info_text"] = new_info
                        current_race["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                        st.success("成功")
                        st.rerun()

    st.markdown(f"#### 第 {selected_race} 場 (Live)")
    
    if not current_race["current_df"].empty:
        df = current_race["current_df"].copy()
        last = current_race["last_df"].copy()
        
        last_odds = last[["現價"]].rename(columns={"現價": "上回"})
        if "上回" not in df.columns:
            df = df.join(last_odds, how="left")
            df["上回"] = df["上回"].fillna(df["現價"])
            
        df["真實走勢(%)"] = ((df["上回"] - df["現價"]) / df["上回"] * 100).fillna(0).round(1)
        df["得分"] = df.apply(calculate_score, axis=1)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index()
        df["信心級別"] = df["得分"].apply(get_level)
        
        st.caption(f"Last Update: {current_race['last_update']}")
        
        tab1, tab2 = st.tabs(["📋 總覽", "📑 明細"])
        
        with tab1:
            max_horse = df.iloc[0]
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("最高評分", f"#{max_horse['馬號']} {max_horse['馬名']}", f"{max_horse['得分']}")
            with c2: st.metric("平均分", f"{df['得分'].mean().round(1)}")
            with c3: st.metric("落飛數", int((df["真實走勢(%)"] > 0).sum()))
            
            top_picks = df[df["得分"] >= top_pick_threshold]
            if not top_picks.empty:
                st.markdown(f"**TOP PICKS (>{top_pick_threshold})**")
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
                                    <span>{row['現價']}</span>
                                    <span style="color:#c62828; font-weight:bold;">{row['得分']}</span>
                                </div>
                                <div style="margin-top:5px; font-size:12px;">{trend_html}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("無 TOP PICKS")

        with tab2:
            st.dataframe(
                df[["馬號", "馬名", "現價", "上回", "真實走勢(%)", "騎師", "練馬師", "得分", "信心級別"]],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("等待數據...")

# ============= History 模式 =============
elif app_mode == "📜 歷史 (History)":
    history_db = load_history()
    if 'selected_date' in locals() and selected_date and history_db and str(selected_history_race) in history_db[selected_date]:
        data = history_db[selected_date][str(selected_history_race)]
        st.markdown(f"#### {selected_date} - R{selected_history_race}")
        
        df_hist = pd.DataFrame(data["odds_data"])
        if "真實走勢(%)" not in df_hist.columns: df_hist["真實走勢(%)"] = 0.0
        df_hist["得分"] = df_hist.apply(calculate_score, axis=1)
        df_hist = df_hist.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        df_hist["信心級別"] = df_hist["得分"].apply(get_level)

        top_picks = df_hist[df_hist["得分"] >= top_pick_threshold]
        if not top_picks.empty:
            st.markdown(f"**TOP PICKS**")
            cols = st.columns(min(len(top_picks), 3))
            for idx, col in enumerate(cols):
                if idx < len(top_picks):
                    row = top_picks.iloc[idx]
                    with col:
                        st.markdown(f"""
                        <div class="horse-card" style="background-color:#f9f9f9;">
                            <div>#{row['馬號']} {row['馬名']} ({row['信心級別']})</div>
                            <div>{row['現價']} <span style="color:#c62828;">({row['得分']})</span></div>
                        </div>
                        """, unsafe_allow_html=True)
        
        st.dataframe(df_hist[["馬號", "馬名", "現價", "真實走勢(%)", "騎師", "練馬師", "得分", "信心級別"]], use_container_width=True, hide_index=True)
    else:
        st.info("無數據")

# ============= Overview 模式 =============
elif app_mode == "📈 今日總覽":
    st.markdown("#### 📈 今日總覽")
    history_db = load_history()
    today_str = datetime.now(HKT).strftime("%Y-%m-%d")
    
    if today_str in history_db:
        daily = history_db[today_str]
        rows = []
        for race_id in range(1, 15):
            race_key = str(race_id)
            if race_key in daily:
                df_r = pd.DataFrame(daily[race_key]["odds_data"])
                if df_r.empty: continue
                if "真實走勢(%)" not in df_r.columns: df_r["真實走勢(%)"] = 0.0
                df_r["得分"] = df_r.apply(calculate_score, axis=1)
                df_r = df_r.sort_values(["得分", "現價"], ascending=[False, True])
                top = df_r.iloc[0]
                top_picks_count = (df_r["得分"] >= top_pick_threshold).sum()
                rows.append({
                    "場次": race_id,
                    "最高評分": f"#{top['馬號']} {top['馬名']} ({top['得分']})",
                    "平均分": df_r["得分"].mean().round(1),
                    "TOP PICKS": int(top_picks_count)
                })
        if rows:
            st.dataframe(pd.DataFrame(rows).sort_values("場次"), use_container_width=True, hide_index=True)
        else:
            st.info("今日無數據")
    else:
        st.info("今日無數據")
