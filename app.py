import streamlit as st
import pandas as pd
import re
import json
import os
import requests
import time
import random
from datetime import datetime, timedelta, timezone, date
from streamlit_autorefresh import st_autorefresh
import lxml
import html5lib

# ===================== 版本 V1.17 (HTML 結構診斷) =====================
APP_VERSION = "V1.17 (Debug Structure)"
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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

JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'K Teetan': 2.8, '田泰安': 2.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K W Lui': 4.0, '呂健威': 4.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'F C Lor': 3.2, '羅富全': 3.2}

def fetch_debug_structure(r_no, t_date):
    date_str = t_date.strftime("%Y/%m/%d")
    url = "https://racing.hkjc.com/racing/information/Chinese/Racing/Local/Odds.aspx"
    venues = ["HV", "ST"]
    
    logs = []
    
    s = requests.Session()
    
    for ven in venues:
        logs.append(f"=== 嘗試場地: {ven}, 日期: {date_str}, 場次: {r_no} ===")
        params = {"RaceDate": date_str, "Racecourse": ven, "RaceNo": r_no}
        
        try:
            resp = s.get(url, params=params, headers=HEADERS, timeout=10)
            logs.append(f"HTTP 狀態: {resp.status_code}")
            
            if resp.status_code == 200:
                t_match = re.search(r'<title>(.*?)</title>', resp.text)
                if t_match:
                    logs.append(f"網頁標題: {t_match.group(1)}")
                
                try:
                    dfs = pd.read_html(resp.content, flavor='html5lib')
                    logs.append(f"找到 {len(dfs)} 個表格")
                    
                    for i, df in enumerate(dfs):
                        cols = list(df.columns)
                        cols_str = str(cols)[:100]
                        logs.append(f"表格 #{i+1} 欄位: {cols_str}")
                        
                        if not df.empty:
                            first_row = str(df.iloc[0].values)[:100]
                            logs.append(f"表格 #{i+1} 第一行: {first_row}")
                            
                except Exception as e:
                    logs.append(f"Pandas 解析失敗: {str(e)}")
                    logs.append(f"HTML Preview: {resp.text[:500]}")
            
        except Exception as e:
            logs.append(f"請求錯誤: {str(e)}")
            
    return None, "\n".join(logs)
def gen_demo():
    rows = []
    for i in range(1, 13):
        rows.append({"馬號": i, "馬名": f"模擬馬 {i}", "現價": round(random.uniform(1.5, 50.0), 1)})
    return pd.DataFrame(rows)

def get_score(row):
    s = 0
    o = row.get("現價", 0)
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
        if k in j or j in k: s += v * 2.5
    for k, v in TRAINER_RANK.items():
        if k in t or t in k: s += v * 1.5
    return round(s, 1)

def get_lvl(s):
    if s >= 80: return "A"
    elif s >= 70: return "B"
    elif s >= 60: return "C"
    else: return "-"

def parse_info(txt):
    rows = []
    if not txt: return pd.DataFrame()
    for line in txt.split('\n'):
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].isdigit():
            try:
                no = int(parts[0])
                chn = [p for p in parts if REGEX_CHN.match(p)]
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

with st.sidebar:
    st.markdown("### 模式")
    app_mode = st.radio("選單", ["📡 實時", "📜 歷史", "📈 總覽"], label_visibility="collapsed")
    st.divider()
    threshold = st.slider("TOP PICKS 門檻", 50, 90, 65)
    
    if app_mode == "📡 實時":
        st.divider()
        sel_date = st.date_input("日期", value=datetime.now(HKT).date())
        sel_race = st.radio("場次", list(range(1, 15)), format_func=lambda x: f"賽事 {x}", horizontal=True)
        st_autorefresh(interval=30000, key="auto_refresh")
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
        if st.button("🔄 執行診斷", type="primary", use_container_width=True):
            if 'use_demo' in locals() and use_demo:
                df_new = gen_demo()
                log = "Demo"
                time.sleep(0.5)
            else:
                df_new, log = fetch_debug_structure(sel_race, sel_date)
            
            curr["debug_info"] = log
            st.error("診斷完成，請查看右側日誌")
    
    with c2: 
        st.info(f"賽事 {sel_race} | 更新: {curr['last_update']}")
        with st.expander("📝 結構診斷 (Debug Structure)", expanded=True):
            st.code(curr["debug_info"])

    if not curr["current_df"].empty:
        pass
    else:
        st.info("請點擊左側「執行診斷」查看 HTML 結構")
