import streamlit as st
import pandas as pd
import re
import json
import os
import requests
import time
from datetime import datetime, timedelta, timezone
from streamlit_autorefresh import st_autorefresh

# ===================== 0. 全局配置 =====================
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://bet.hkjc.com",
    "Referer": "https://bet.hkjc.com/",
    "Content-Type": "application/json"
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

# 評分權重
JOCKEY_RANK = {'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'K Teetan': 2.8, '田泰安': 2.8}
TRAINER_RANK = {'J Size': 4.4, '蔡約翰': 4.4, 'K W Lui': 4.0, '呂健威': 4.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'F C Lor': 3.2, '羅富全': 3.2}

# ===================== 1. 核心 API (安全寫法) =====================
def fetch_hkjc_data(race_no):
    """
    獲取 HKJC 賠率，使用 .get() 方法避免 SyntaxError
    """
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    url = "https://bet.hkjc.com/racing/getJSON.aspx"
    
    # 嘗試 ST
    params = {"type": "winodds", "date": today, "venue": "ST", "start": race_no, "end": race_no}
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
    except:
        return None, "網絡連線失敗"

    # 檢查是否需要切換 HV
    use_hv = False
    if resp.status_code != 200:
        use_hv = True
    else:
        # 使用變數承接，避免直接在 if 判斷中出錯
        txt_content = resp.text
        if "OUT" not in txt_content:
            use_hv = True
            
    if use_hv:
        params["venue"] = "HV"
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        except:
            return None, "網絡連線失敗 (HV)"
            
    if resp.status_code != 200:
        return None, f"伺服器錯誤 {resp.status_code}"

    # 解析 JSON
    data = None
    try:
        data = resp.json()
    except:
        return None, "數據格式錯誤"

    if data is None:
        return None, "數據為空"

    # 安全獲取 OUT 欄位
    raw_str = data.get("OUT")
    
    if not raw_str:
        return None, "無賠率數據 (OUT 缺失)"
        
    # 解析字串
    odds_list = []
    parts = raw_str.split(";")
    for p in parts:
        if "=" in p:
            kv = p.split("=")
            if len(kv) == 2:
                k, v = kv
                if k.isdigit():
                    try:
                        val = float(v)
                        if val < 900:
                            odds_list.append({"馬號": int(k), "現價": val})
                    except: pass
    
    if odds_list:
        df = pd.DataFrame(odds_list)
        df["馬名"] = df["馬號"].apply(lambda x: f"馬匹 {x}")
        return df, None
        
    return None, "解析後無有效賠率"

# ===================== 2. 輔助函數 =====================
def get_score(row):
    s = 0
    # 賠率分
    o = row.get("現價", 0)
    if o > 0 and o <= 5.0: s += 25
    elif o > 5.0 and o <= 10.0: s += 10
    
    # 走勢分
    tr = row.get("走勢", 0)
    if tr >= 15: s += 50
    elif tr >= 10: s += 35
    elif tr >= 5: s += 20
    elif tr <= -10: s -= 20
    
    # 人馬分
    j = str(row.get("騎師", ""))
    t = str(row.get("練馬師", ""))
    for k, v in JOCKEY_RANK.items():
        if k in j or j in k: s += v * 2.5
    for k, v in TRAINER_RANK.items():
        if k in t or t in k: s += v * 1.5
        
    return round(s, 1)

def get_level(s):
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

def save_history_data(store):
    d_data = {}
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    for r, v in store.items():
        if not v["current_df"].empty:
            d_data[str(r)] = {
                "odds": v["current_df"].to_dict(orient="records"),
                "info": v["raw_info_text"],
                "time": v["last_update"]
            }
    if d_
        full = {}
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f: full = json.load(f)
            except: pass
        full[today] = d_data
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(full, f, ensure_ascii=False, indent=4)
        return True, "已成功封存今日數據"
    return False, "無數據可封存"

def load_history_data():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {}

# ===================== 3. UI 界面 =====================
st.set_page_config(page_title="HKJC 賽馬智腦 (Pro)", layout="wide")

# CSS 美化 (恢復您喜歡的卡片樣式)
st.markdown("""
<style>
    .stApp { background-color: #f5f7f9; color: #000000 !important; font-family: sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #ddd; }
    .main-title { color: #1a237e; font-weight: 800; font-size: 28px; letter-spacing: 1px; }
    
    /* 卡片樣式 */
    .horse-card { background-color: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd; border-top: 4px solid #1a237e; margin-bottom: 8px; }
    .top-pick-card { border-top: 4px solid #c62828; }
    
    /* 標籤樣式 */
    .tag { display: inline-block; padding: 2px 6px; border-radius: 2px; font-size: 11px; font-weight: bold; }
    .tag-drop { background-color: #ffebee; color: #c62828; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32; } 
    .tag-lvl { background-color: #1a237e; color: white; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="border-bottom: 2px solid #1a237e; padding-bottom: 5px; margin-bottom: 10px;">
    <span class="main-title">賽馬智腦</span>
    <span style="font-size:14px; color:#fff; background-color:#1a237e; padding:3px 8px; border-radius:4px; margin-left:8px; vertical-align:middle;">API Enhanced</span>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 模式")
    app_mode = st.radio("功能", ["📡 實時 (Live)", "📜 歷史 (History)", "📈 今日總覽"], label_visibility="collapsed")
    st.divider()
    
    threshold = st.slider("TOP PICKS 門檻", 50, 90, 65)
    
    if app_mode == "📡 實時 (Live)":
        st.divider()
        sel_race = st.selectbox("選擇場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        st_autorefresh(interval=30000, key="auto_refresh")
        
        st.divider()
        if st.button("💾 封存今日數據", use_container_width=True):
            ok, msg = save_history_data(race_storage)
            if ok: st.success(msg)
            else: st.warning(msg)

# 邏輯處理
if app_mode == "📡 實時 (Live)":
    curr = race_storage[sel_race]
    
    # 頂部控制列
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 立即更新賠率 (API)", type="primary", use_container_width=True):
            df_new, err = fetch_hkjc_data(sel_race)
            if df_new is not None:
                # 嘗試保留排位資料
                if not curr["current_df"].empty:
                    old = curr["current_df"]
                    if "騎師" in old.columns:
                        info_cols = old[["馬號", "騎師", "練馬師"]]
                        df_new = df_new.merge(info_cols, on="馬號", how="left").fillna("未知")
                    # 保留非預設的馬名
                    if "馬名" in old.columns:
                        # 簡單邏輯: 如果舊表有馬名且不是 "馬匹 X"，就用舊的
                        # 這裡簡化處理：直接用 merge 覆蓋
                        pass

                # 計算走勢
                if not curr["current_df"].empty:
                    last = curr["current_df"][["馬號", "現價"]].rename(columns={"現價": "上回"})
                    df_new = df_new.merge(last, on="馬號", how="left")
                    df_new["上回"] = df_new["上回"].fillna(df_new["現價"])
                    df_new["走勢"] = ((df_new["上回"] - df_new["現價"]) / df_new["上回"] * 100).fillna(0).round(1)
                else:
                    df_new["走勢"] = 0.0
                
                curr["current_df"] = df_new
                curr["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                st.success("數據已更新")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(err)
    
    with c2:
        st.info(f"上次更新: {curr['last_update']}")

    # 排位輸入區 (保留功能)
    with st.expander("🛠️ 補充排位資料 (馬名/騎師/練馬師)"):
        txt_input = st.text_area("排位表文字", value=curr["raw_info_text"], height=100)
        if st.button("更新排位資料"):
            info_df = parse_info(txt_input)
            if not info_df.empty and not curr["current_df"].empty:
                main_df = curr["current_df"]
                # 刪除舊的
                if "騎師" in main_df.columns: main_df = main_df.drop(columns=["騎師", "練馬師"])
                # 合併
                main_df = main_df.merge(info_df, on="馬號", how="left").fillna("未知")
                curr["current_df"] = main_df
                curr["raw_info_text"] = txt_input
                st.success("排位資料已合併")
                st.rerun()

    # 主顯示區
    if not curr["current_df"].empty:
        df = curr["current_df"]
        df["得分"] = df.apply(get_score, axis=1)
        df["級別"] = df["得分"].apply(get_level)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        
        tab1, tab2 = st.tabs(["📋 卡片視圖", "📑 詳細列表"])
        
        with tab1:
            best = df.iloc[0]
            m1, m2, m3 = st.columns(3)
            m1.metric("最高評分", f"#{best['馬號']} ({best['得分']})")
            m2.metric("平均分", round(df["得分"].mean(), 1))
            m3.metric("落飛馬匹", int((df["走勢"] > 0).sum()))
            
            picks = df[df["得分"] >= threshold]
            if not picks.empty:
                st.markdown(f"**🔥 重點推薦 (>{threshold})**")
                cols = st.columns(min(3, len(picks)))
                for i, col in enumerate(cols):
                    if i < len(picks):
                        r = picks.iloc[i]
                        trend = r['走勢']
                        tag_c = "tag-drop" if trend > 0 else "tag-rise"
                        txt = f"落飛 {trend}%" if trend > 0 else f"回飛 {abs(trend)}%"
                        if trend == 0: txt = "-"
                        
                        with col:
                            st.markdown(f"""
                            <div class="horse-card top-pick-card">
                                <div style="display:flex; justify-content:space-between">
                                    <b>#{r['馬號']} {r.get('馬名','')}</b>
                                    <span class="tag tag-lvl">{r['級別']}級</span>
                                </div>
                                <div style="font-size:20px; font-weight:bold; margin:8px 0">
                                    {r['現價']} <span style="color:#c62828; float:right">{r['得分']}</span>
                                </div>
                                <div class="tag {tag_c}">{txt}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("暫無高分推薦")

        with tab2:
            st.dataframe(df, use_container_width=True)
    else:
        st.info("⚠️ 暫無數據，請點擊上方的「立即更新賠率」")

elif app_mode == "📜 歷史 (History)":
    st.markdown("#### 📜 歷史回顧")
    h_db = load_history_data()
    if h_db:
        dates = sorted(h_db.keys(), reverse=True)
        sel_d = st.selectbox("日期", dates)
        if sel_d:
            races = sorted([int(x) for x in h_db[sel_d].keys()])
            sel_r = st.selectbox("場次", races, format_func=lambda x: f"第 {x} 場")
            if sel_r:
                raw = h_db[sel_d][str(sel_r)]["odds"]
                hist_df = pd.DataFrame(raw)
                hist_df["得分"] = hist_df.apply(get_score, axis=1)
                hist_df["級別"] = hist_df["得分"].apply(get_level)
                st.dataframe(hist_df.sort_values("得分", ascending=False), use_container_width=True)
    else:
        st.info("暫無歷史存檔")

elif app_mode == "📈 今日總覽":
    st.markdown("#### 📈 今日總覽")
    h_db = load_history_data()
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    
    if today in h_db:
        res = []
        for rid, val in h_db[today].items():
            tmp = pd.DataFrame(val["odds"])
            if not tmp.empty:
                tmp["得分"] = tmp.apply(get_score, axis=1)
                best = tmp.sort_values("得分", ascending=False).iloc[0]
                res.append({
                    "場次": rid, 
                    "首選": f"#{best['馬號']} ({best['得分']})",
                    "賠率": best['現價']
                })
        
        if res:
            res_df = pd.DataFrame(res)
            # 按場次排序
            res_df["場次"] = res_df["場次"].astype(int)
            st.table(res_df.sort_values("場次"))
    else:
        st.info("今日尚未封存任何數據 (請先在 Live 模式封存)")
