import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.73 (Multi-Race Data Center) =====================
# 重大升級：支援儲存與查看「多場」比賽。
# 前台新增：場次選擇下拉選單。
# 資料結構：改為字典儲存 { "2025-12-17_1": df, "2025-12-17_2": df ... }

st.set_page_config(page_title="賽馬智腦 V1.73", layout="wide")

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

# --- 排位解析器 (V1.72) ---
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

# --- 賠率解析器 (V1.71) ---
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

# --- Session Initialization ---
# [關鍵] race_database: 儲存多場比賽的字典
if 'race_database' not in st.session_state: st.session_state['race_database'] = {}
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
# 預設顯示的日期場次 (給後台用)
if 'current_edit_info' not in st.session_state: st.session_state['current_edit_info'] = {"date": datetime.now().date(), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.73")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入") and pwd == "jay123":
            st.session_state['admin_logged_in'] = True
            st.rerun()
    else:
        st.subheader("1. 選擇要編輯的場次")
        c_d, c_r = st.columns(2)
        with c_d: 
            d_in = st.date_input("日期", value=st.session_state['current_edit_info']['date'])
        with c_r: 
            r_in = st.number_input("場次", 1, 14, st.session_state['current_edit_info']['no'])
            
        # 生成唯一的 Key，例如 "2025-12-17_Race_1"
        race_key = f"{d_in}_Race_{r_in}"
        
        st.divider()
        st.subheader(f"2. 輸入資料: {d_in} 第 {r_in} 場")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.info("排位表 (最終版格式)")
            card_in = st.text_area("排位文字", height=300, key=f"card_{race_key}")
        with c2: 
            st.info("賠率 (垂直格式)")
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
                
                # [關鍵] 將資料存入字典，Key 為場次ID
                st.session_state['race_database'][race_key] = {
                    "df": df,
                    "date": str(d_in),
                    "race_no": r_in,
                    "update_time": pd.Timestamp.now().strftime("%H:%M:%S")
                }
                
                # 更新當前編輯狀態
                st.session_state['current_edit_info'] = {"date": d_in, "no": r_in}
                st.success(f"成功發布！目前資料庫共有 {len(st.session_state['race_database'])} 場比賽。")
            else: st.error("排位表解析失敗")

else:
    # --- 公眾看板 ---
    st.title("📊 賽事分析中心")
    
    # 檢查是否有任何資料
    if not st.session_state['race_database']:
        st.info("📭 目前暫無賽事資料，請等待管理員發布。")
    else:
        # [關鍵] 下拉選單：列出所有已發布的比賽
        # 排序：按日期和場次排序
        race_keys = list(st.session_state['race_database'].keys())
        race_keys.sort() # 簡單排序字串
        
        # 顯示選單
        selected_key = st.selectbox(
            "請選擇比賽場次：",
            options=race_keys,
            format_func=lambda x: f"{st.session_state['race_database'][x]['date']} - 第 {st.session_state['race_database'][x]['race_no']} 場"
        )
        
        # 根據選擇取出對應的資料
        race_data = st.session_state['race_database'][selected_key]
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
        st.caption(f"最後更新: {race_data['update_time']}")
