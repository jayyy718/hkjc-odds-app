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

# ===================== 版本 V1.14 =====================
APP_VERSION = "V1.14"
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

# 兩組 Headers：桌面版 與 手機版
HEADERS_DESKTOP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
    "Referer": "https://bet.hkjc.com/racing/pages/odds_wp.aspx?lang=en",
    "Connection": "keep-alive"
}

HEADERS_MOBILE = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "*/*",
    "Referer": "https://m.hkjc.com/"
}

@st.cache_resource
def get_regex():
    return (re.compile(r'^\d+$'), re.compile(r'\d+\.?\d*'), re.compile(r'[\u4e00-\u9fa5]+'))

REGEX_INT, REGEX_FLOAT, REGEX_CHN = get_regex()

@st.cache_resource
def get_storage():
    data = {}
    for i in range(1, 15):
        data[i] = {
            "current_df": pd.DataFrame(),
            "last_df": pd.DataFrame(),
            "last_update": "無數據",
            "raw_info_text": ""
        }
    return data

race_storage = get_storage()

JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'K Teetan': 2.8, '田泰安': 2.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K W Lui': 4.0, '呂健威': 4.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'F C Lor': 3.2, '羅富全': 3.2}

def get_json_odds(session, r_no, d_str, ven):
    # 策略 1: 標準 JSON API
    url = "https://bet.hkjc.com/racing/getJSON.aspx"
    params = {"type": "winodds", "date": d_str, "venue": ven, "start": r_no, "end": r_no}
    try:
        # 隨機延遲，模擬真人
        time.sleep(random.uniform(0.1, 0.3))
        resp = session.get(url, params=params, headers=HEADERS_DESKTOP, timeout=6)
        
        if resp.status_code == 200 and "OUT" in resp.text:
            data = resp.json()
            raw = data.get("OUT")
            if raw:
                res = []
                for p in raw.split(";"):
                    if "=" in p:
                        k, v = p.split("=")
                        if k.isdigit():
                            try:
                                val = float(v)
                                if val < 900: res.append({"馬號": int(k), "現價": val})
                            except: pass
                if res: return res
    except: pass
    return None

def get_html_odds(session, r_no, d_str, ven):
    # 策略 2: 爬取網頁 HTML (桌面版)
    url = "https://bet.hkjc.com/racing/pages/odds_wp.aspx"
    params = {"date": d_str, "venue": ven, "raceno": r_no, "lang": "en"}
    try:
        time.sleep(random.uniform(0.1, 0.3))
        resp = session.get(url, params=params, headers=HEADERS_DESKTOP, timeout=8)
        
        if resp.status_code == 200:
            res = []
            # 增強型 Regex: 抓取 id="win_odds_1" 或類似結構
            pat = r'(?:id="win_odds_|o=")(\d+)"[^>]*>([\d\.]+)<'
            matches = re.findall(pat, resp.text)
            
            # 如果上面抓不到，試試看抓 JS 變數
            if not matches:
                pat_js = r'winodds\s*=\s*"([^"]+)"'
                m_js = re.search(pat_js, resp.text)
                if m_js:
                    raw = m_js.group(1)
                    for p in raw.split(";"):
                        if "=" in p:
                            k, v = p.split("=")
                            if k.isdigit():
                                matches.append((k, v))

            if matches:
                for m in matches:
                    try:
                        h = int(m[0])
                        v = float(m[1])
                        if v < 900: res.append({"馬號": h, "現價": v})
                    except: pass
                if res: return res
    except: pass
    return None

def fetch_data(r_no, t_date):
    d_str = t_date.strftime("%Y-%m-%d")
    s = requests.Session()
    
    # 1. 訪問首頁種 Cookie (非常重要)
    try: 
        s.get("https://bet.hkjc.com/index.aspx?lang=en", headers=HEADERS_DESKTOP, timeout=5)
    except: pass
    
    err = ""
    # 輪詢場地
    for v in ["ST", "HV"]:
        # 先試 JSON
        d = get_json_odds(s, r_no, d_str, v)
        # 失敗則試 HTML
        if not d:
            d = get_html_odds(s, r_no, d_str, v)
        
        if d:
            df = pd.DataFrame(d)
            df["馬名"] = df["馬號"].apply(lambda x: f"馬匹 {x}")
            return df, None
        else:
            err = f"API 無回應 (日期: {d_str}, 場地: {v})"
            
    return None, err
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
        # [修復] 日期選擇器預設為明天 (因為通常是為了預覽)
        # 或者讓用戶自己選
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
        if st.button("🔄 更新賠率", type="primary", use_container_width=True):
            if 'use_demo' in locals() and use_demo:
                df_new = gen_demo()
                err = None
                time.sleep(0.5)
            else:
                df_new, err = fetch_data(sel_race, sel_date)
            
            if df_new is not None:
                if not curr["current_df"].empty:
                    old = curr["current_df"]
                    if "騎師" in old.columns:
                        info_cols = old[["馬號", "騎師", "練馬師"]]
                        df_new = df_new.merge(info_cols, on="馬號", how="left").fillna("未知")
                    last = curr["current_df"][["馬號", "現價"]].rename(columns={"現價": "上回"})
                    df_new = df_new.merge(last, on="馬號", how="left")
                    df_new["上回"] = df_new["上回"].fillna(df_new["現價"])
                    df_new["走勢"] = ((df_new["上回"] - df_new["現價"]) / df_new["上回"] * 100).fillna(0).round(1)
                else: df_new["走勢"] = 0.0
                curr["current_df"] = df_new
                curr["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                st.success("已更新")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"失敗：{err}")
    
    with c2: st.info(f"賽事 {sel_race} | 更新: {curr['last_update']}")

    with st.expander("🛠️ 排位資料"):
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
            m2.metric("平均", round(df["得分"].mean(), 1))
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
                            st.markdown(f"""
                            <div class="horse-card top-pick-card">
                                <div style="display:flex; justify-content:space-between">
                                    <b style="color:#000;">#{r['馬號']} {r.get('馬名','')}</b>
                                    <span class="tag tag-lvl">{r['級別']}級</span>
                                </div>
                                <div style="font-size:20px; font-weight:bold; margin:8px 0; color:#000;">
                                    {r['現價']} <span style="color:#c62828; float:right">{r['得分']}</span>
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
