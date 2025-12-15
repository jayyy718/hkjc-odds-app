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

# 評分字典
JOCKEY_RANK = { 'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 'C Williams': 5.9, '韋紀力': 5.9, 'R Moore': 5.9, '莫雅': 5.9, 'H Bowman': 4.8, '布文': 4.8, 'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'R Kingscote': 3.8, '金美琪': 3.8, 'A Atzeni': 3.7, '艾兆禮': 3.7, 'B Avdulla': 3.7, '艾道拿': 3.7, 'P N Wong': 3.4, '黃寶妮': 3.4, 'T Marquand': 3.3, '馬昆': 3.3, 'H Doyle': 3.3, '杜苑欣': 3.3, 'E C W Wong': 3.2, '黃智弘': 3.2, 'K C Leung': 3.2, '梁家俊': 3.2, 'B Shinn': 3.0, '薛恩': 3.0, 'K Teetan': 2.8, '田泰安': 2.8, 'H Bentley': 2.7, '班德禮': 2.7, 'M F Poon': 2.6, '潘明輝': 2.6, 'C L Chau': 2.4, '周俊樂': 2.4, 'M Chadwick': 2.4, '蔡明紹': 2.4, 'A Badel': 2.4, '巴度': 2.4, 'L Hewitson': 2.3, '希威森': 2.3, 'J Orman': 2.2, '奧文': 2.2, 'K De Melo': 1.9, '董明朗': 1.9, 'M L Yeung': 1.8, '楊明綸': 1.8, 'Y L Chung': 1.8, '鍾易禮': 1.8, 'A Hamelin': 1.7, '賀銘年': 1.7, 'H T Mo': 1.3, '巫顯東': 1.3, 'B Thompson': 0.9, '湯普新': 0.9, 'A Pouchin': 0.8, '普珍宜': 0.8 }
TRAINER_RANK = { 'J Size': 4.4, '蔡約翰': 4.4, 'K L Man': 4.3, '文家良': 4.3, 'K W Lui': 4.0, '呂健威': 4.0, 'D Eustace': 3.9, '游達榮': 3.9, 'C Fownes': 3.9, '方嘉柏': 3.9, 'P F Yiu': 3.7, '姚本輝': 3.7, 'D A Hayes': 3.7, '大衛希斯': 3.7, 'M Newnham': 3.6, '廖康銘': 3.6, 'W Y So': 3.4, '蘇偉賢': 3.4, 'W K Mo': 3.3, '巫偉傑': 3.3, 'F C Lor': 3.2, '羅富全': 3.2, 'C H Yip': 3.2, '葉楚航': 3.2, 'C S Shum': 3.1, '沈集成': 3.1, 'K H Ting': 3.1, '丁冠豪': 3.1, 'A S Cruz': 3.0, '告東尼': 3.0, 'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'Y S Tsui': 2.5, '徐雨石': 2.5, 'J Richards': 2.3, '黎昭昇': 2.3, 'D J Hall': 2.3, '賀賢': 2.3, 'C W Chang': 2.2, '鄭俊偉': 2.2, 'T P Yung': 2.1, '容天鵬': 2.1 }

# ===================== 核心 API (安全修復版) =====================
def fetch_hkjc_data(race_no):
    try:
        today = datetime.now(HKT).strftime("%Y-%m-%d")
        url = "https://bet.hkjc.com/racing/getJSON.aspx"
        
        # 嘗試沙田
        p1 = {"type": "winodds", "date": today, "venue": "ST", "start": race_no, "end": race_no}
        try:
            resp = requests.get(url, params=p1, headers=HEADERS, timeout=5)
        except:
            return None, "網絡異常"

        # 判斷是否需要切換到 HV (分開寫，避免語法錯誤)
        need_hv = False
        if resp.status_code != 200:
            need_hv = True
        elif "OUT" not in resp.text:
            need_hv = True
            
        if need_hv:
            p2 = {"type": "winodds", "date": today, "venue": "HV", "start": race_no, "end": race_no}
            try:
                resp = requests.get(url, params=p2, headers=HEADERS, timeout=5)
            except:
                return None, "網絡異常 (HV)"
        
        if resp.status_code != 200:
            return None, "伺服器錯誤"

        # 解析 JSON
        try:
            data = resp.json()
        except:
            return None, "非 JSON 格式"

        # 安全檢查 data 是否為 None
        if data is None:
            return None, "數據為空"

        # 檢查 key 是否存在 (這是你之前報錯的地方)
        has_out = False
        if "OUT" in 
            has_out = True
            
        if not has_out:
            return None, "無賠率數據 (OUT 缺失)"
            
        raw_str = data["OUT"]
        if not raw_str:
            return None, "賠率字串為空"

        parts = raw_str.split(";")
        odds_list = []
        for item in parts:
            if "=" in item:
                kv = item.split("=")
                if len(kv) == 2:
                    k_str = kv[0]
                    v_str = kv[1]
                    if k_str.strip().isdigit():
                        try:
                            k = int(k_str)
                            v = float(v_str)
                            if v < 900:
                                odds_list.append({"馬號": k, "現價": v})
                            else:
                                # 999 視為無效或退賽
                                pass 
                        except:
                            continue
        
        if len(odds_list) > 0:
            df = pd.DataFrame(odds_list)
            df["馬名"] = df["馬號"].apply(lambda x: f"馬匹 {x}")
            return df, None
        else:
            return None, "解析後無有效賠率"

    except Exception as e:
        return None, str(e)

# ===================== 輔助函數 =====================
def save_history(store):
    if not os.path.exists(HISTORY_FILE):
        hist = {}
    else:
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                hist = json.load(f)
        except:
            hist = {}
            
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    day_data = {}
    for r_id, val in store.items():
        if not val["current_df"].empty:
            day_data[str(r_id)] = {
                "odds_data": val["current_df"].to_dict(orient="records"),
                "info": val["raw_info_text"],
                "time": val["last_update"]
            }
            
    if day_
        hist[today] = day_data
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(hist, f, indent=4, ensure_ascii=False)
        return True, "已儲存"
    return False, "無數據"

def load_hist():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except: return {}
    return {}

def get_score(row):
    s = 0
    # 走勢
    tr = row.get("走勢", 0)
    if tr >= 15: s += 50
    elif tr >= 10: s += 35
    elif tr >= 5: s += 20
    elif tr <= -10: s -= 20
    
    # 賠率
    o = row.get("現價", 0)
    if o > 0 and o <= 5.0: s += 25
    elif o > 5.0 and o <= 10.0: s += 10
    
    # 人馬
    j = row.get("騎師", "")
    t = row.get("練馬師", "")
    
    # 模糊匹配
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
                # 簡單邏輯: 假設有兩個以上中文詞，第二個是騎師，第三個是練馬師
                # 或者如果有名字像騎師表裡的，就匹配
                j_name = "未知"
                t_name = "未知"
                
                if len(chn) >= 2:
                    j_name = chn[1] if len(chn) > 1 else "未知"
                    t_name = chn[2] if len(chn) > 2 else "未知"
                
                rows.append({"馬號": no, "騎師": j_name, "練馬師": t_name})
            except: continue
    if rows: return pd.DataFrame(rows)
    return pd.DataFrame()

# ===================== UI 設置 =====================
st.set_page_config(page_title="HKJC 賽馬智腦 (Pro)", layout="wide")

# 樣式
st.markdown("""
<style>
    .stApp { background-color: #f5f7f9; color: #000000 !important; font-family: sans-serif; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #ddd; }
    .horse-card { background-color: white; padding: 12px; border-radius: 6px; border: 1px solid #ddd; border-top: 4px solid #1a237e; margin-bottom: 8px; }
    .top-card { border-top: 4px solid #c62828; }
    .tag { display: inline-block; padding: 2px 6px; border-radius: 2px; font-size: 11px; font-weight: bold; }
    .tag-drop { background-color: #ffebee; color: #c62828; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32; } 
    .tag-lvl { background-color: #1a237e; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("賽馬智腦 (HKJC API)")

# Sidebar
with st.sidebar:
    mode = st.radio("功能", ["📡 實時 (Live)", "📜 歷史 (History)", "📈 今日總覽"])
    st.divider()
    threshold = st.slider("TOP PICKS 門檻", 50, 90, 65)
    
    if mode == "📡 實時 (Live)":
        r_idx = st.selectbox("場次", range(1, 15), format_func=lambda x: f"第 {x} 場")
        st_autorefresh(interval=30000, key="refresh")
        
        st.divider()
        if st.button("💾 封存今日數據"):
            ok, msg = save_history(race_storage)
            if ok: st.success(msg)
            else: st.warning(msg)

# Logic
if mode == "📡 實時 (Live)":
    cur = race_storage[r_idx]
    
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("🔄 立即更新賠率 (API)", type="primary", use_container_width=True):
            df_new, err = fetch_hkjc_data(r_idx)
            if df_new is not None:
                # 合併排位
                if not cur["current_df"].empty:
                    old_df = cur["current_df"]
                    # 如果舊的有騎師練馬師，保留
                    if "騎師" in old_df.columns:
                        info_part = old_df[["馬號", "騎師", "練馬師"]]
                        df_new = df_new.merge(info_part, on="馬號", how="left")
                        df_new = df_new.fillna("未知")
                    # 如果有馬名，保留
                    if "馬名" in old_df.columns:
                        # 避免覆蓋
                        pass
                
                # 計算走勢需要上一回數據
                if not cur["current_df"].empty:
                    cur["last_df"] = cur["current_df"]
                else:
                    cur["last_df"] = df_new
                
                cur["current_df"] = df_new
                cur["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
                st.success("已更新")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(err)

    with c2:
        st.info(f"Last Update: {cur['last_update']}")

    # 排位輸入
    with st.expander("🛠️ 補充排位資料 (馬名/騎師)"):
        txt = st.text_area("排位表", value=cur["raw_info_text"], height=100)
        if st.button("更新排位"):
            d_info = parse_info(txt)
            if not d_info.empty:
                cur["raw_info_text"] = txt
                # 合併進 current_df
                if not cur["current_df"].empty:
                    main_df = cur["current_df"]
                    # 先刪除舊的
                    if "騎師" in main_df.columns: main_df = main_df.drop(columns=["騎師", "練馬師"])
                    # 合併
                    new_df = main_df.merge(d_info, on="馬號", how="left")
                    new_df = new_df.fillna("未知")
                    cur["current_df"] = new_df
                    st.success("排位已合併")
                    st.rerun()
                else:
                    st.warning("請先按上方按鈕獲取賠率數據，再更新排位")

    # 顯示
    if not cur["current_df"].empty:
        df = cur["current_df"].copy()
        last = cur["last_df"].copy()
        
        # 準備走勢
        last_s = last[["馬號", "現價"]].rename(columns={"現價": "上回"})
        if "上回" not in df.columns:
            df = df.merge(last_s, on="馬號", how="left")
            df["上回"] = df["上回"].fillna(df["現價"])
            
        df["走勢"] = ((df["上回"] - df["現價"]) / df["上回"] * 100).fillna(0).round(1)
        df["得分"] = df.apply(get_score, axis=1)
        df["級別"] = df["得分"].apply(get_lvl)
        df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index(drop=True)
        
        t1, t2 = st.tabs(["卡片視圖", "詳細列表"])
        
        with t1:
            best = df.iloc[0]
            c_a, c_b, c_c = st.columns(3)
            c_a.metric("最高評分", f"#{best['馬號']} ({best['得分']})")
            c_b.metric("平均分", round(df["得分"].mean(), 1))
            c_c.metric("落飛數", int((df["走勢"] > 0).sum()))
            
            picks = df[df["得分"] >= threshold]
            if not picks.empty:
                st.write(f"**🔥 TOP PICKS (>{threshold})**")
                cols = st.columns(min(3, len(picks)))
                for i, col in enumerate(cols):
                    if i < len(picks):
                        r = picks.iloc[i]
                        tr = r['走勢']
                        tag_cls = "tag-drop" if tr > 0 else "tag-rise"
                        txt = f"落飛 {tr}%" if tr > 0 else f"回飛 {abs(tr)}%"
                        if tr == 0: txt = "-"
                        
                        with col:
                            st.markdown(f"""
                            <div class="horse-card top-card">
                                <div style="display:flex; justify-content:space-between">
                                    <b>#{r['馬號']} {r.get('馬名','')}</b>
                                    <span class="tag tag-lvl">{r['級別']}</span>
                                </div>
                                <div style="font-size:18px; font-weight:bold; margin:5px 0">
                                    {r['現價']} <span style="color:#c62828; margin-left:10px">{r['得分']}</span>
                                </div>
                                <div class="tag {tag_cls}">{txt}</div>
                            </div>
                            """, unsafe_allow_html=True)
            else:
                st.info("暫無高分推薦")

        with t2:
            st.dataframe(df, use_container_width=True)
    else:
        st.info("暫無數據，請按「更新賠率」")

elif mode == "📜 歷史 (History)":
    h = load_hist()
    if h:
        d = st.selectbox("日期", sorted(h.keys(), reverse=True))
        if d:
            rr = st.selectbox("場次", sorted([int(k) for k in h[d].keys()]))
            if rr:
                raw = h[d][str(rr)]["odds_data"]
                dh = pd.DataFrame(raw)
                dh["得分"] = dh.apply(get_score, axis=1)
                st.dataframe(dh.sort_values("得分", ascending=False), use_container_width=True)
    else:
        st.info("無存檔")

elif mode == "📈 今日總覽":
    h = load_hist()
    today = datetime.now(HKT).strftime("%Y-%m-%d")
    if today in h:
        res = []
        for rid, v in h[today].items():
            tmp = pd.DataFrame(v["odds_data"])
            if not tmp.empty:
                tmp["得分"] = tmp.apply(get_score, axis=1)
                top = tmp.sort_values("得分", ascending=False).iloc[0]
                res.append({"R": rid, "Best": f"#{top['馬號']} ({top['得分']})"})
        st.table(pd.DataFrame(res))
    else:
        st.info("今日未有存檔")
