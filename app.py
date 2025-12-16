import streamlit as st
import pandas as pd
import re
import json
import os
import requests
import time
import random
from bs4 import BeautifulSoup # 引入手術刀
from datetime import datetime, timedelta, timezone, date
from streamlit_autorefresh import st_autorefresh

# ===================== 版本 V1.29 (BeautifulSoup) =====================
APP_VERSION = "V1.29 (Raw HTML Surgery)"
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

# 擴充關鍵字庫
JOCKEY_KEYWORDS = ['Purton', 'McDonald', 'Bowman', 'Teetan', 'Ho', 'Bentley', 'Ferraris', 'Hamelin', 'Atzeni', 'De Sousa', 'Avdulla', 'Mo', 'Wong', 'Chau', 'Yeung', 'Poon', 'Badel', 'Hewitson']
TRAINER_KEYWORDS = ['Size', 'Lui', 'Hayes', 'Lor', 'Yip', 'Yiu', 'Fownes', 'Whyte', 'Hall', 'Newnham', 'Richards', 'Man', 'Shum', 'So', 'Tsui', 'Ng', 'Chang']

JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'K Teetan': 2.8, '田泰安': 2.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K W Lui': 4.0, '呂健威': 4.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'F C Lor': 3.2, '羅富全': 3.2}

def fetch_scmp_bs4(r_no, t_date):
    date_str = t_date.strftime("%Y%m%d")
    url = f"https://racing.scmp.com/racing/race-card/{date_str}/race/{r_no}"
    logs = [f"SCMP (BS4): {url}"]
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            tables = soup.find_all('table')
            logs.append(f"找到 {len(tables)} 個表格 (Raw HTML)")
            
            target_table = None
            max_rows = 0
            
            # 尋找行數最多的表格
            for tbl in tables:
                rows = tbl.find_all('tr')
                # 排位表通常在 8-18 行之間
                if len(rows) >= 8 and len(rows) <= 20:
                    if len(rows) > max_rows:
                        max_rows = len(rows)
                        target_table = tbl
            
            if target_table:
                logs.append(f"-> 鎖定 {max_rows} 行的表格，開始解剖...")
                
                rows = target_table.find_all('tr')
                res = []
                
                # 掃描每一行
                for r_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    # 提取純文字
                    row_data = [c.get_text(strip=True) for c in cells]
                    
                    if not row_ continue
                    
                    # 判斷這行是不是馬匹數據行
                    # 條件：必須包含一個可能是馬號的數字 (1-14)，且長度足夠
                    # 或包含騎師/練馬師關鍵字
                    
                    # 嘗試識別各個欄位
                    h_no = 0
                    h_name = "未知"
                    jock = "未知"
                    trn = "未知"
                    odds = 0.0
                    
                    is_valid_row = False
                    
                    for i, txt in enumerate(row_data):
                        # 1. 找馬號 (通常在第0或1格，純數字)
                        if h_no == 0 and re.match(r'^\d+$', txt):
                            val = int(txt)
                            if 1 <= val <= 24: # 合理馬號範圍
                                h_no = val
                                is_valid_row = True
                        
                        # 2. 找騎師
                        if jock == "未知" and any(k in txt for k in JOCKEY_KEYWORDS):
                            jock = txt
                            is_valid_row = True
                            
                        # 3. 找練馬師
                        if trn == "未知" and any(k in txt for k in TRAINER_KEYWORDS):
                            trn = txt
                            is_valid_row = True
                            
                        # 4. 找馬名 (全大寫英文，排除 LAST RUNS 這種標題)
                        if h_name == "未知" and re.match(r'^[A-Z\s\']+$', txt) and len(txt) > 3:
                            if "LAST RUNS" not in txt and "HORSE" not in txt and "JOCKEY" not in txt:
                                # 排除騎師練馬師名字
                                if not any(k.upper() in txt for k in JOCKEY_KEYWORDS + TRAINER_KEYWORDS):
                                    h_name = txt
                                    is_valid_row = True
                                    
                        # 5. 找賠率 (小數點)
                        if odds == 0.0 and re.match(r'^\d+\.\d+$', txt):
                            try:
                                v = float(txt)
                                if 1.0 < v < 200.0: # 合理賠率範圍
                                    odds = v
                            except: pass

                    # 特殊處理：黏連修復 (例如 "1PERFECT PAIRING")
                    # 如果找不到馬號，檢查第一個有內容的格子
                    if h_no == 0:
                        for txt in row_
                            if txt:
                                m = re.match(r'^(\d+)([A-Z\s]+)$', txt)
                                if m:
                                    h_no = int(m.group(1))
                                    if h_name == "未知": h_name = m.group(2).strip()
                                    is_valid_row = True
                                    break

                    if is_valid_row and h_no > 0:
                        # 清理數據
                        jock = re.sub(r'\s*\(.*?\)', '', jock)
                        
                        res.append({
                            "馬號": h_no,
                            "馬名": h_name,
                            "騎師": jock,
                            "練馬師": trn,
                            "現價": odds
                        })
                
                if res:
                    logs.append(f"成功提取 {len(res)} 匹馬")
                    # 預覽第一匹
                    logs.append(f"First: {res[0]}")
                    return pd.DataFrame(res), "\n".join(logs)
                else:
                    logs.append("雖然找到表格，但無法識別任何馬匹數據 (HTML 結構可能變異)")
                    # Debug: 印出第一行的 raw text
                    if len(rows) > 1:
                         first_row_cells = rows[1].find_all(['td', 'th'])
                         logs.append(f"Row 1 Raw: {[c.get_text(strip=True) for c in first_row_cells]}")

            else:
                logs.append("找不到符合行數條件的表格")
                
    except Exception as e:
        logs.append(f"BS4 Error: {e}")
        
    return None, "\n".join(logs)
def fetch_hkjc_fallback_log(r_no):
    """只記錄 HKJC 狀態，不依賴"""
    url = "https://bet.hkjc.com/racing/jsonData.aspx"
    try:
        params = {"type": "winodds", "date": datetime.now(HKT).strftime("%Y-%m-%d"), "venue": "HV", "start": r_no, "end": r_no}
        requests.get(url, params=params, headers=HEADERS, timeout=3)
    except: pass
    return {}

def fetch_data(r_no, t_date):
    full_log = "=== 開始更新 ===\n"
    
    # 1. SCMP 手術刀解析
    df, log = fetch_scmp_bs4(r_no, t_date)
    full_log += log + "\n"
    
    if df is not None and not df.empty:
        # 賠率補救：如果 SCMP 沒抓到賠率 (全0)，試試 HKJC
        if df["現價"].sum() == 0:
            full_log += "SCMP 賠率缺失，嘗試 HKJC 正則補位...\n"
            try:
                # 這裡重用之前的 HKJC regex 邏輯，但放在這裡避免代碼太長
                url = "https://bet.hkjc.com/racing/jsonData.aspx"
                params = {"type": "winodds", "date": datetime.now(HKT).strftime("%Y-%m-%d"), "venue": "HV", "start": r_no, "end": r_no}
                resp = requests.get(url, params=params, headers=HEADERS, timeout=4)
                odds_map = {}
                matches = re.findall(r'\b(\d+)=([\d\.]+)', resp.text)
                for m in matches: odds_map[int(m[0])] = float(m[1])
                if not odds_map:
                    matches = re.findall(r'"(\d+)":"([\d\.]+)"', resp.text)
                    for m in matches: odds_map[int(m[0])] = float(m[1])
                
                if odds_map:
                    df["現價"] = df["馬號"].map(odds_map).fillna(0.0)
                    full_log += f"HKJC 補位成功: {len(odds_map)} 筆\n"
                else:
                    full_log += "HKJC 無數據\n"
            except: pass
            
        return df, full_log
        
    return None, full_log + "SCMP 解析失敗\n"

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
        if st.button("🔄 手術刀更新 (BS4)", type="primary", use_container_width=True):
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
        with st.expander("📝 解剖日誌 (Surgery Log)", expanded=True):
            st.code(curr["debug_info"])

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
