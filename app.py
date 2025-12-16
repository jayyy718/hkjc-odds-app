import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.76 (Cache Fix Edition) =====================
# 修復 AttributeError：透過重新命名快取函數 (get_database_v2) 
# 強制系統建立包含 clear_all 功能的全新資料庫物件。

st.set_page_config(page_title="賽馬智腦 V1.76", layout="wide")

# --- 核心數據 (不變) ---
REAL_STATS = {
    "jockey": { "Z Purton": 22.9, "J McDonald": 21.3, "M Barzalona": 16.7, "J Moreira": 16.1, "C Williams": 14.8, "H Bowman": 14.5, "K Teetan": 12.0, "C Y Ho": 11.5, "A Badel": 8.5, "A Atzeni": 8.2, "L Hewitson": 7.8, "B Avdulla": 7.5, "Y L Chung": 7.2, "C L Chau": 6.8, "K C Leung": 5.5, "M F Poon": 5.2, "H Bentley": 9.5, "L Ferraris": 8.0, "M Chadwick": 6.5, "A Hamelin": 4.5 },
    "trainer": { "J Size": 11.0, "K L Man": 10.9, "K W Lui": 10.0, "D Eustace": 9.8, "C Fownes": 9.7, "P C Ng": 9.5, "F C Lor": 9.2, "D A Hayes": 8.8, "A S Cruz": 8.5, "C S Shum": 8.3, "P F Yiu": 8.0, "D J Hall": 7.8, "M Newnham": 7.5, "W K Mo": 7.2, "J Richards": 6.5, "W Y So": 6.2, "T P Yung": 5.5, "Y S Tsui": 4.5, "C H Yip": 4.0, "C W Chang": 3.5 }
}
NAME_MAPPING = { "麥道朗": "J McDonald", "潘頓": "Z Purton", "布文": "H Bowman", "艾道拿": "B Avdulla", "金誠剛": "M Barzalona", "希威森": "L Hewitson", "鍾易禮": "Y L Chung", "田泰安": "K Teetan", "周俊樂": "C L Chau", "杜苑欣": "H Doyle", "蔡約翰": "J Size", "伍鵬志": "P C Ng", "方嘉柏": "C Fownes", "大衛希斯": "D A Hayes", "黎昭昇": "J Richards", "鄭俊偉": "C W Chang", "蘇偉賢": "W Y So", "告東尼": "A S Cruz", "徐雨石": "Y S Tsui", "葉楚航": "C H Yip", "丁冠豪": "K H Ting", "文家良": "K L Man", "潘大衛": "D Egan", "奧爾民": "J Orman" }

def calculate_ai_score(row):
    score = 0
    try:
        odds = float(row['獨贏'])
        if odds > 0: score += ((1 / odds) * 100) * 0.7 
    except: pass
    j_name = re.sub(r'\s*\([+-]?\d+\)', '', str(row.get('騎師', ''))).strip()
    j_en = NAME_MAPPING.get(j_name, j_name if re.search(r'[a-zA-Z]', j_name) else "")
    if j_en in REAL_STATS["jockey"]: score += REAL_STATS["jockey"][j_en] * 0.6
    t_name = str(row.get('練馬師', '')).strip()
    t_en = NAME_MAPPING.get(t_name, "")
    if t_en in REAL_STATS["trainer"]: score += REAL_STATS["trainer"][t_en] * 0.4
    try:
        draw = int(row['檔位'])
        if draw <= 3: score += 5
        elif draw >= 11: score -= 3
    except: pass
    return score

def parse_card_v172(text):
    data = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or "馬匹編號" in line: continue
        parts = re.split(r'\s+', line)
        if not parts[0].isdigit(): continue
        try:
            row = {}
            row['馬號'] = int(parts[0])
            row['6次近績'] = parts[1]
            row['馬名'] = parts[2]
            row['負磅'] = int(parts[3])
            idx = 4
            jockey = parts[idx]
            idx += 1
            if idx < len(parts) and "(-" in parts[idx]:
                jockey += " " + parts[idx]
                idx += 1
            row['騎師'] = jockey
            if idx < len(parts) and parts[idx].isdigit():
                row['檔位'] = int(parts[idx])
                idx += 1
            if idx < len(parts):
                row['練馬師'] = parts[idx]
                idx += 1
            if idx < len(parts):
                row['評分'] = parts[idx]
            data.append(row)
        except: continue
    return pd.DataFrame(data)

def parse_odds_strict_sequence(text):
    odds_map = {}
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.isdigit() and 1 <= int(line) <= 14:
            current = int(line)
            if i + 2 < len(lines):
                win_line = lines[i+2]
                try:
                    nums = re.findall(r'\d+\.\d+|\d+', win_line)
                    if nums: odds_map[current] = float(nums[0])
                except: pass
            i += 2 
        else: i += 1
    return odds_map

# ===================== 全域資料庫 (v2) =====================
class RaceDatabase:
    def __init__(self):
        self.races = {} 
    
    def clear_all(self):
        self.races = {}

# [修復關鍵] 改名為 get_database_v2，強制 Streamlit 重新建立物件
@st.cache_resource
def get_database_v2():
    return RaceDatabase()

db = get_database_v2()

if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
if 'current_edit_info' not in st.session_state: st.session_state['current_edit_info'] = {"date": datetime.now().date(), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.76")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入") and pwd == "jay123":
            st.session_state['admin_logged_in'] = True
            st.rerun()
    else:
        # --- 重置按鈕區 ---
        with st.expander("⚠️ 危險操作區"):
            if st.button("🗑️ 清空所有賽事資料 (重置系統)", type="secondary"):
                try:
                    db.clear_all()
                    st.success("資料庫已清空，您可以開始輸入新賽日的資料了。")
                    # 強制重新整理頁面以反映變更
                    st.rerun()
                except Exception as e:
                    st.error(f"重置失敗: {e}")
                
        st.subheader("1. 選擇要編輯的場次")
        c_d, c_r = st.columns(2)
        with c_d: 
            d_in = st.date_input("日期", value=st.session_state['current_edit_info']['date'])
        with c_r: 
            r_in = st.number_input("場次", 1, 14, st.session_state['current_edit_info']['no'])
            
        race_key = f"{d_in}_Race_{r_in}"
        
        st.divider()
        st.subheader(f"2. 輸入資料: {d_in} 第 {r_in} 場")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.info("排位表")
            card_in = st.text_area("排位文字", height=300, key=f"card_{race_key}")
        with c2: 
            st.info("賠率")
            odds_in = st.text_area("賠率文字", height=300, key=f"odds_{race_key}")
            
        if st.button(f"🚀 發布第 {r_in} 場資料", type="primary"):
            df = parse_card_v172(card_in)
            if not df.empty:
                if odds_in:
                    odds_map = parse_odds_strict_sequence(odds_in)
                    df['獨贏'] = df['馬號'].map(odds_map).fillna("-")
                else: df['獨贏'] = "-"
                
                scores = []
                for _, row in df.iterrows(): scores.append(calculate_ai_score(row))
                df['AI分數'] = scores
                total = sum(scores)
                df['勝率%'] = (df['AI分數']/total*100).round(1) if total>0 else 0.0
                
                db.races[race_key] = {
                    "df": df,
                    "date": str(d_in),
                    "race_no": r_in,
                    "update_time": pd.Timestamp.now().strftime("%H:%M:%S")
                }
                
                st.session_state['current_edit_info'] = {"date": d_in, "no": r_in}
                st.success(f"成功發布！目前資料庫共有 {len(db.races)} 場比賽。")
            else: st.error("排位表解析失敗")

else:
    st.title("📊 賽事分析中心")
    if not db.races:
        st.info("📭 目前暫無資料。請管理員輸入新賽事。")
    else:
        race_keys = list(db.races.keys())
        race_keys.sort()
        
        selected_key = st.selectbox(
            "請選擇比賽場次：",
            options=race_keys,
            format_func=lambda x: f"{db.races[x]['date']} - 第 {db.races[x]['race_no']} 場"
        )
        
        race_data = db.races[selected_key]
        df = race_data['df'].copy()
        
        st.markdown(f"### 🏁 {race_data['date']} 第 {race_data['race_no']} 場")
        
        df = df.sort_values('勝率%', ascending=False).reset_index(drop=True)
        top4 = df.head(4)
        cols = st.columns(4)
        for i, col in enumerate(cols):
            if i < len(top4):
                h = top4.iloc[i]
                col.metric(f"#{h['馬號']} {h['馬名']}", f"{h['勝率%']}%", f"賠率: {h['獨贏']}")
        
        st.divider()
        display_cols = [c for c in ['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅', '評分', '6次近績'] if c in df.columns]
        
        st.dataframe(
            df[display_cols],
            column_config={
                "勝率%": st.column_config.ProgressColumn("AI 勝率", format="%.1f%%", min_value=0, max_value=100),
                "獨贏": st.column_config.TextColumn("獨贏賠率"),
                "馬號": st.column_config.NumberColumn("No.", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"最後更新: {race_data['update_time']} (全網同步)")
