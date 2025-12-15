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

# ----------------- 全局配置 -----------------
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/",
    "Content-Type": "application/json"
}

@st.cache_resource
def get_static_resources():
    return (re.compile(r'^\d+$'), re.compile(r'\d+\.?\d*'), re.compile(r'[\u4e00-\u9fa5]+'))

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

JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'C Williams': 5.9, '韋紀力': 5.9, 'R Moore': 5.9, '莫雅': 5.9, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'R Kingscote': 3.8, '金美琪': 3.8, 'A Atzeni': 3.7, '艾兆禮': 3.7, 'B Avdulla': 3.7, '艾道拿': 3.7, 'P N Wong': 3.4, '黃寶妮': 3.4, 'T Marquand': 3.3, '馬昆': 3.3, 'H Doyle': 3.3, '杜苑欣': 3.3, 'E C W Wong': 3.2, '黃智弘': 3.2, 'K C Leung': 3.2, '梁家俊': 3.2, 'B Shinn': 3.0, '薛恩': 3.0, 'K Teetan': 2.8, '田泰安': 2.8, 'H Bentley': 2.7, '班德禮': 2.7, 'M F Poon': 2.6, '潘明輝': 2.6, 'C L Chau': 2.4, '周俊樂': 2.4, 'M Chadwick': 2.4, '蔡明紹': 2.4, 'A Badel': 2.4, '巴度': 2.4, 'L Hewitson': 2.3, '希威森': 2.3, 'J Orman': 2.2, '奧文': 2.2, 'K De Melo': 1.9, '董明朗': 1.9, 'M L Yeung': 1.8, '楊明綸': 1.8, 'Y L Chung': 1.8, '鍾易禮': 1.8, 'A Hamelin': 1.7, '賀銘年': 1.7, 'H T Mo': 1.3, '巫顯東': 1.3, 'B Thompson': 0.9, '湯普新': 0.9, 'A Pouchin': 0.8, '普珍宜': 0.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K L Man': 4.3, '文家良': 4.3, 'K W Lui': 4.0, '呂健威': 4.0, 'D Eustace': 3.9, '游達榮': 3.9, 'C Fownes': 3.9, '方嘉柏': 3.9, 'P F Yiu': 3.7, '姚本輝': 3.7, 'D A Hayes': 3.7, '大衛希斯': 3.7, 'M Newnham': 3.6, '廖康銘': 3.6, 'W Y So': 3.4, '蘇偉賢': 3.4, 'W K Mo': 3.3, '巫偉傑': 3.3, 'F C Lor': 3.2, '羅富全': 3.2, 'C H Yip': 3.2, '葉楚航': 3.2, 'C S Shum': 3.1, '沈集成': 3.1, 'K H Ting': 3.1, '丁冠豪': 3.1, 'A S Cruz': 3.0, '告東尼': 3.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'Y S Tsui': 2.5, '徐雨石': 2.5, 'J Richards': 2.3, '黎昭昇': 2.3, 'D J Hall': 2.3, '賀賢': 2.3, 'C W Chang': 2.2, '鄭俊偉': 2.2, 'T P Yung': 2.1, '容天鵬': 2.1}

# ----------------- 核心函數 -----------------
def fetch_hkjc_data(race_no):
    try:
        today_str = datetime.now(HKT).strftime("%Y-%m-%d")
        url = "https://bet.hkjc.com/racing/getJSON.aspx"
        params = {"type": "winodds", "date": today_str, "venue": "ST", "start": race_no, "end": race_no}
        
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
            if resp.status_code != 200 or "OUT" not in resp.text:
                params["venue"] = "HV"
                resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        except:
            return None, "Network Error"

        if resp.status_code == 200:
            try:
                data = resp.json()
            except:
                return None, "JSON Error"

            if data and "OUT" in 
                raw_str = data["OUT"]
                parts = raw_str.split(";")
                odds_list = []
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=")
                        if k.isdigit():
                            try:
                                val = float(v)
                                real_val = val if val < 900 else 0.0
                                odds_list.append({"馬號": int(k), "現價": real_val})
                            except:
                                continue
                
                if odds_list:
                    df = pd.DataFrame(odds_list)
                    df["馬名"] = df["馬號"].apply(lambda x: f"馬匹 {x}")
                    return df, None
            return None, "No Data (OUT key missing)"
        return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)

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

# ----------------- 頁面 UI -----------------
st.set_page_config(page_title="HKJC 賽馬智腦 (Fixed)", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f5f7f9; color: #000000 !important; font-family: sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #ddd; }
    .horse-card { background-color: white; padding: 10px; border-radius: 6px; border: 1px solid #ddd; border-top: 4px solid #1a237e; margin-bottom: 8px; }
    .top-pick-card { border-top: 4px solid #c62828; }
    .status-tag { display: inline-block; padding: 2px 6px; border-radius: 2px; font-size: 11px; font-weight: bold; }
    .tag-drop { background-color: #ffebee; color: #c62828; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32; } 
    .tag-top { background-color: #1a237e; color: white; }    
</style>
""", unsafe_allow_html=True)

st.title("賽馬智腦 (HKJC API)")

with st.sidebar:
    app_mode = st.radio("功能", ["📡 實時 (Live)", "📜 歷史 (History)", "📈 今日總覽"])
    st.divider()
    top_pick_threshold = st.slider("TOP PICKS 門檻", 50, 85, 65, 1)
    if app_mode == "📡 實時 (Live)":
        selected_race = st.selectbox("選擇場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        st_autorefresh(interval=30000, key="live_refresh")
    
    st.divider()
    if st.button("💾 封存今日數據"):
        s, m = save_daily_history(race_storage)
        if s: st.success("已封存")
        else: st.warning(m)

if app_mode == "📡 實時 (Live)":
    current = race_storage[selected_race]
    
    if st.button("🔄 立即更新賠率 (API)", type="primary"):
        df, err = fetch_hkjc_data(selected_race)
        if df is not None:
            if not current["current_df"].empty:
                old = current["current_df"][["馬號", "馬名", "騎師", "練馬師"]]
                df = df.drop(columns=["馬名"], errors='ignore').merge(old, on="馬號", how="left")
                df["馬名"] = df["馬名"].fillna(df["馬號"].apply(lambda x: f"馬匹 {x}"))
            
            if not current["current_df"].empty: current["last_df"] = current["current_df"]
            else: current["last_df"] = df
            
            current["current_df"] = df
            current["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
            st.success("更新成功")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error(f"更新失敗: {err}")

    st.info(f"Last Update: {current['last_update']}")

    with st.expander("🛠️ 手動輸入排位資料 (補充馬名/騎師)"):
        with st.form(f"f_{selected_race}"):
            txt = st.text_area("排位表", value=current["raw_info_text"])
            if st.form_submit_button("更新資料"):
                d_info = parse_info_data(txt)
                if not d_info.empty and not current["current_df"].empty:
                    d_curr = current["current_df"]
                    for c in ["騎師", "練馬師"]: 
                        if c in d_curr.columns: d_curr = d_curr.drop(columns=[c])
                    d_new = d_curr.merge(d_info, on="馬號", how="left").fillna("未知")
                    current["current_df"] = d_new
                    current["raw_info_text"] = txt
                    st.success("資料已合併")
                    st.rerun()

    if not current["current_df"].empty:
        df = current["current_df"].copy()
        last = current["last_df"].copy()
        
        for c in ["騎師", "練馬師"]: 
            if c not in df.columns: df[c] = "未知"
            
        l_odds = last[["馬號", "現價"]].rename(columns={"現價": "上回"})
        if "上回" not in df.columns:
            df = df.merge(l_odds, on="馬號", how="left")
            df["上回"] = df["上回"].fillna(df["現價"])
            
        df["真實走勢(%)"] = ((df["上回"] - df["現價"]) / df["上回"] * 100).fillna(0).round(1)
        df["得分"] = df.apply(calculate_score, axis=1)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        df["信心級別"] = df["得分"].apply(get_level)
        
        tab1, tab2 = st.tabs(["總覽", "列表"])
        with tab1:
            top = df.iloc[0]
            c1, c2 = st.columns(2)
            c1.metric("最高評分", f"#{top['馬號']} ({top['得分']})")
            c2.metric("落飛數", int((df["真實走勢(%)"] > 0).sum()))
            
            picks = df[df["得分"] >= top_pick_threshold]
            if not picks.empty:
                st.write(f"**TOP PICKS (>{top_pick_threshold})**")
                cols = st.columns(min(len(picks), 3))
                for i, col in enumerate(cols):
                    if i < len(picks):
                        r = picks.iloc[i]
                        with col:
                            st.markdown(f"""
                            <div class="horse-card top-pick-card">
                                <b>#{r['馬號']} {r.get('馬名','')}</b><br>
                                <span style="font-size:18px">{r['現價']}</span> 
                                <span style="color:red;font-weight:bold">Score: {r['得分']}</span>
                            </div>
                            """, unsafe_allow_html=True)
        with tab2:
            st.dataframe(df, use_container_width=True)
    else:
        st.info("暫無數據")

elif app_mode == "📜 歷史 (History)":
    h_db = load_history()
    if h_db:
        d = st.selectbox("日期", sorted(h_db.keys(), reverse=True))
        if d:
            r = st.selectbox("場次", sorted([int(k) for k in h_db[d].keys()]))
            if r:
                dd = pd.DataFrame(h_db[d][str(r)]["odds_data"])
                dd["得分"] = dd.apply(calculate_score, axis=1)
                st.dataframe(dd.sort_values("得分", ascending=False), use_container_width=True)
    else:
        st.info("無歷史")

elif app_mode == "📈 今日總覽":
    h_db = load_history()
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    if today in h_db:
        rows = []
        for r_id, val in h_db[today].items():
            t_df = pd.DataFrame(val["odds_data"])
            if not t_df.empty:
                t_df["得分"] = t_df.apply(calculate_score, axis=1)
                best = t_df.sort_values("得分", ascending=False).iloc[0]
                rows.append({"R": r_id, "Best": f"#{best['馬號']} ({best['得分']})"})
        st.table(pd.DataFrame(rows))
    else:
        st.info("今日無數據")
