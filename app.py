import streamlit as st
import pandas as pd
import re
import requests
import time
import random
import os
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

# ===================== 版本 V1.36 (Final Single Block) =====================
APP_VERSION = "V1.36 (Stable)"
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

@st.cache_resource
def get_storage():
    data = {}
    for i in range(1, 15):
        data[i] = {
            "current_df": pd.DataFrame(),
            "last_df": pd.DataFrame(),
            "last_update": "無數據",
            "raw_info_text": "",
            "debug_info": ""
        }
    return data

race_storage = get_storage()

JOCKEY_DB = [
    'Z Purton', 'Purton', 'J McDonald', 'McDonald', 'H Bowman', 'Bowman', 
    'K Teetan', 'Teetan', 'C Y Ho', 'Ho', 'L Ferraris', 'Ferraris', 
    'H Bentley', 'Bentley', 'A Badel', 'Badel', 'M Chadwick', 'Chadwick',
    'A Atzeni', 'Atzeni', 'L Hewitson', 'Hewitson', 'K De Melo', 'De Melo',
    'B Avdulla', 'Avdulla', 'M F Poon', 'Poon', 'K H Chan', 'Chan',
    'E C W Wong', 'Wong', 'H T Mo', 'Mo', 'C L Chau', 'Chau'
]

TRAINER_DB = [
    'J Size', 'Size', 'K W Lui', 'Lui', 'P C Ng', 'Ng', 'F C Lor', 'Lor',
    'C S Shum', 'Shum', 'P F Yiu', 'Yiu', 'A S Cruz', 'Cruz', 'C Fownes', 'Fownes',
    'D J Whyte', 'Whyte', 'D J Hall', 'Hall', 'M Newnham', 'Newnham',
    'J Richards', 'Richards', 'K L Man', 'Man', 'W Y So', 'So', 'T P Yung', 'Yung',
    'Y S Tsui', 'Tsui', 'C H Yip', 'Yip', 'C W Chang', 'Chang'
]

JOCKEY_RANK = {'Purton': 9.5, 'McDonald': 9.0, 'Bowman': 8.5, 'Teetan': 7.5, 'Ho': 8.0, 'Ferraris': 6.5, 'Bentley': 7.0}
TRAINER_RANK = {'Size': 9.0, 'Lui': 8.5, 'Ng': 8.5, 'Lor': 8.0, 'Shum': 8.0, 'Yiu': 7.5, 'Cruz': 8.5, 'Fownes': 8.0}

def get_score(row):
    s = 0
    o = row.get("現價", 0)
    if o <= 0: return 0
    if o > 0 and o <= 5.0: s += 25
    elif o > 5.0 and o <= 10.0: s += 10
    
    tr = row.get("走勢", 0)
    if tr >= 15: s += 50
    elif tr >= 10: s += 35
    elif tr >= 5: s += 20
    elif tr <= -10: s -= 20
    
    j = str(row.get("騎師", ""))
    t = str(row.get("練馬師", ""))
    
    for k, v in JOCKEY_RANK.items():
        if k in j: s += v * 2.5
    for k, v in TRAINER_RANK.items():
        if k in t: s += v * 1.5
    return round(s, 1)

def get_lvl(s):
    if s >= 80: return "A"
    elif s >= 70: return "B"
    elif s >= 60: return "C"
    else: return "-"

def extract_horse_data_from_text(text):
    """從純文字中挖掘馬匹數據"""
    lines = text.split('\n')
    res = []
    current_horse = {}
    
    # 匹配 "1  ROMANTIC WARRIOR"
    horse_pattern = re.compile(r'^(\d{1,2})\s+([A-Z\s\']{3,30})$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        m = horse_pattern.match(line)
        if m:
            if current_horse:
                res.append(current_horse)
            
            h_no = int(m.group(1))
            h_name = m.group(2).strip()
            
            if h_name not in ["HORSE", "JOCKEY", "TRAINER", "LAST RUNS"]:
                current_horse = {
                    "馬號": h_no,
                    "馬名": h_name,
                    "騎師": "未知",
                    "練馬師": "未知",
                    "現價": 0.0
                }
        
        elif current_horse:
            # 找騎師
            if current_horse["騎師"] == "未知":
                for j in JOCKEY_DB:
                    if j in line:
                        current_horse["騎師"] = j
                        break
            
            # 找練馬師
            if current_horse["練馬師"] == "未知":
                for t in TRAINER_DB:
                    if t in line:
                        current_horse["練馬師"] = t
                        break
                        
            # 找賠率
            if current_horse["現價"] == 0.0:
                odds_match = re.search(r'\b(\d+\.\d+)\b', line)
                if odds_match:
                    try:
                        val = float(odds_match.group(1))
                        if 1.0 < val < 200.0:
                            current_horse["現價"] = val
                    except: pass

    if current_horse:
        res.append(current_horse)
        
    return res

def fetch_scmp_text_mining(r_no, t_date):
    date_str = t_date.strftime("%Y%m%d")
    url = f"https://racing.scmp.com/racing/race-card/{date_str}/race/{r_no}"
    logs = [f"SCMP Text: {url}"]
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            main_content = soup.find('div', class_='racecard') 
            if not main_content:
                main_content = soup.find('body')
            
            raw_text = main_content.get_text(separator='\n')
            data = extract_horse_data_from_text(raw_text)
            
            if 
                logs.append(f"挖掘成功: {len(data)} 匹馬")
                df = pd.DataFrame(data)
                return df, "\n".join(logs)
            else:
                logs.append("挖掘失敗")
                logs.append(f"Preview: {raw_text[:100]}...")
        else:
            logs.append(f"HTTP Error: {resp.status_code}")
    except Exception as e:
        logs.append(f"Error: {e}")
        
    return None, "\n".join(logs)

def fetch_data(r_no, t_date):
    full_log = "=== V1.36 更新 ===\n"
    df, log = fetch_scmp_text_mining(r_no, t_date)
    full_log += log + "\n"
    
    if df is not None and not df.empty:
        # HKJC 補位
        if df["現價"].sum() == 0:
            full_log += "HKJC 補位...\n"
            try:
                url = "https://bet.hkjc.com/racing/jsonData.aspx"
                params = {"type": "winodds", "date": datetime.now(HKT).strftime("%Y-%m-%d"), "venue": "HV", "start": r_no, "end": r_no}
                resp = requests.get(url, params=params, headers=HEADERS, timeout=3)
                odds_map = {}
                matches = re.findall(r'(\d+)\s*=\s*(\d+\.\d+)', resp.text)
                for m in matches: odds_map[int(m[0])] = float(m[1])
                if not odds_map:
                    matches = re.findall(r'"(\d+)"\s*:\s*"(\d+\.\d+)"', resp.text)
                    for m in matches: odds_map[int(m[0])] = float(m[1])
                if odds_map:
                    df["現價"] = df["馬號"].map(odds_map).fillna(0.0)
                    full_log += f"HKJC OK: {len(odds_map)}\n"
            except: pass
        return df, full_log
    return None, full_log

def parse_info(txt):
    rows = []
    if not txt: return pd.DataFrame()
    for line in txt.split('\n'):
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].isdigit():
            try:
                no = int(parts[0])
                chn = [p for p in parts if re.match(r'[\u4e00-\u9fa5]+', p)]
                j = chn[1] if len(chn) > 1 else "未知"
                t = chn[2] if len(chn) > 2 else "未知"
                rows.append({"馬號": no, "騎師": j, "練馬師": t})
            except: pass
    if rows: return pd.DataFrame(rows)
    return pd.DataFrame()

def save_hist(store):
    ex = {}
    td = datetime.now(HKT).strftime("%Y-%m-%d")
    for r, v in store.items():
        if not v["current_df"].empty:
            ex[str(r)] = {
                "odds": v["current_df"].to_dict(orient="records"),
                "info": v["raw_info_text"],
                "time": v["last_update"]
            }
    if ex:
        full = {}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f: full = json.load(f)
            except: pass
        full[td] = ex
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(full, f, ensure_ascii=False, indent=4)
            return True, "已封存"
        except Exception as e: return False, str(e)
    return False, "無數據"

def load_hist():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

# UI
st.set_page_config(page_title=f"賽馬智腦 {APP_VERSION}", layout="wide")
st.markdown("""
<style>
    .stApp, .stApp > header { background-color: #f5f7f9 !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, 
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6, .stMarkdown span,
    .stText, .stCode, div[data-testid="stMetricLabel"], div[data-testid="stMetricValue"],
    .stCaption { color: #000000 !important; }
    section[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e0e0e0; }
    section[data-testid="stSidebar"] * { color: #333333 !important; }
    div[data-testid="stDataFrame"] div[role="grid"] { color: #000000 !important; background-color: #ffffff !important; }
    .horse-card { background-color: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd; border-top: 4px solid #1a237e; margin-bottom: 8px; color: #000000 !important; }
    .top-pick-card { border-top: 4px solid #c62828; }
    .tag { display: inline-block; padding: 2px 6px; border-radius: 2px; font-size: 11px; font-weight: bold; }
    .tag-drop { background-color: #ffebee; color: #c62828 !important; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32 !important; } 
    .tag-lvl { background-color: #1a237e; color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div style="border-bottom: 2px solid #1a237e; padding-bottom: 5px; margin-bottom: 10px;"><span style="color:#1a237e;font-weight:800;font-size:28px;">賽馬智腦</span><span style="font-size:14px;color:#fff;background-color:#1a237e;padding:3px 8px;border-radius:4px;margin-left:8px;">{APP_VERSION}</span></div>', unsafe_allow_html=True)

def gen_demo():
    rows = []
    for i in range(1, 13):
        rows.append({"馬號": i, "馬名": f"模擬馬 {i}", "現價": round(random.uniform(1.5, 50.0), 1)})
    return pd.DataFrame(rows)

with st.sidebar:
    st.markdown("### 模式")
    app_mode = st.radio("選單", ["📡 實時", "📜 歷史", "📈 總覽"], label_visibility="collapsed")
    st.divider()
    threshold = st.slider("TOP PICKS 門檻", 50, 90, 65)
    
    if app_mode == "📡 實時":
        st.divider()
        sel_date = st.date_input("日期", value=datetime.now(HKT).date())
        sel_race = st.radio("場次", list(range(1, 15)), format_func=lambda x: f"賽事 {x}", horizontal=True)
        st.divider()
        if st.button("💾 封存數據"):
            ok, msg = save_hist(race_storage)
            if ok: st.success(msg)
            else: st.warning(msg)
        st.divider()
        use_demo = st.checkbox("🧪 測試模式")

if app_mode == "📡 實時":
    curr = race_storage[sel_race]
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 更新數據", type="primary", use_container_width=True):
            if 'use_demo' in locals() and use_demo:
                df_new = gen_demo()
                log = "Demo"
                time.sleep(0.5)
            else:
                df_new, log = fetch_data(sel_race, sel_date)
            
            curr["debug_info"] = log
            
            if df_new is not None:
                if not curr["current_df"].empty:
                    last = curr["current_df"][["馬號", "現價"]].rename(columns={"現價": "上回"})
                    df_new = df_new.merge(last, on="馬號", how="left")
                    df_new["上回"] = df_new["上回"].fillna(df_new["現價"])
                    df_new["走勢"] = ((df_new["上回"] - df_new["現價"]) / df_new["上回"] * 100).fillna(0).round(1)
                else: 
                    df_new["走勢"] = 0.0
                
                curr["current_df"] = df_new
                curr["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                st.success("成功")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("失敗")
    
    with c2: 
        st.info(f"賽事 {sel_race} | 更新: {curr['last_update']}")
        with st.expander("📝 執行日誌", expanded=True):
            st.code(curr["debug_info"])

    with st.expander("🛠️ 排位資料 (手動修正)"):
        txt_input = st.text_area("貼上排位表", value=curr["raw_info_text"], height=100)
        if st.button("合併資料"):
            info_df = parse_info(txt_input)
            if not info_df.empty and not curr["current_df"].empty:
                main_df = curr["current_df"]
                if "騎師" in main_df.columns: main_df = main_df.drop(columns=["騎師", "練馬師"])
                main_df = main_df.merge(info_df, on="馬號", how="left").fillna("未知")
                curr["current_df"] = main_df
                curr["raw_info_text"] = txt_input
                st.success("OK")
                st.rerun()

    if not curr["current_df"].empty:
        df = curr["current_df"]
        df["得分"] = df.apply(get_score, axis=1)
        df["級別"] = df["得分"].apply(get_lvl)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        
        tab1, tab2 = st.tabs(["📋 卡片", "📑 列表"])
        with tab1:
            best = df.iloc[0]
            m1, m2, m3 = st.columns(3)
            m1.metric("最高分", f"#{best['馬號']} ({best['得分']})")
            
            valid = df[df["現價"] > 0]
            m2.metric("平均", round(valid["得分"].mean(), 1) if not valid.empty else 0)
            m3.metric("落飛", int((df["走勢"] > 0).sum()))
            
            picks = df[df["得分"] >= threshold]
            if not picks.empty:
                st.markdown(f"**🔥 推薦 (>{threshold})**")
                cols = st.columns(min(3, len(picks)))
                for i, col in enumerate(cols):
                    if i < len(picks):
                        r = picks.iloc[i]
                        trend = r['走勢']
                        tag_c = "tag-drop" if trend > 0 else "tag-rise"
                        txt = f"落 {trend}%" if trend > 0 else f"回 {abs(trend)}%"
                        if trend == 0: txt = "-"
                        with col:
                            p_disp = r['現價'] if r['現價'] > 0 else "未開"
                            st.markdown(f"""
                            <div class="horse-card top-pick-card">
                                <div style="display:flex; justify-content:space-between">
                                    <b style="color:#000;">#{r['馬號']} {r.get('馬名','')}</b>
                                    <span class="tag tag-lvl">{r['級別']}級</span>
                                </div>
                                <div style="font-size:20px; font-weight:bold; margin:8px 0; color:#000;">
                                    {p_disp} <span style="color:#c62828; float:right">{r['得分']}</span>
                                </div>
                                <div class="tag {tag_c}">{txt}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else: st.info("無推薦")

        with tab2: st.dataframe(df, use_container_width=True)
    else:
        st.info("暫無數據")

elif app_mode == "📜 歷史":
    h_db = load_hist()
    if h_db:
        dates = sorted(h_db.keys(), reverse=True)
        sel_d = st.selectbox("日期", dates)
        if sel_d:
            races = sorted([int(x) for x in h_db[sel_d].keys()])
            sel_r = st.radio("場次", races, format_func=lambda x: f"賽事 {x}", horizontal=True)
            if sel_r:
                raw = h_db[sel_d][str(sel_r)]["odds"]
                hist_df = pd.DataFrame(raw)
                hist_df["得分"] = hist_df.apply(get_score, axis=1)
                hist_df["級別"] = hist_df["得分"].apply(get_lvl)
                st.dataframe(hist_df.sort_values("得分", ascending=False), use_container_width=True)
    else: st.info("無存檔")

elif app_mode == "📈 總覽":
    h_db = load_hist()
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    if today in h_db:
        res = []
        for rid, val in h_db[today].items():
            tmp = pd.DataFrame(val["odds"])
            if not tmp.empty:
                tmp["得分"] = tmp.apply(get_score, axis=1)
                best = tmp.sort_values("得分", ascending=False).iloc[0]
                res.append({"場次": int(rid), "首選": f"#{best['馬號']} ({best['得分']})", "賠率": best['現價']})
        if res: st.table(pd.DataFrame(res).sort_values("場次"))
    else: st.info("無今日數據")
