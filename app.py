import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.69 (The Perfect UI Fix) =====================
# 修復項目：
# 1. 加回 Admin 後台的「日期」與「場次」輸入。
# 2. 加回前端表格的「獨贏」欄位顯示。
# 3. 保留 V1.68 的強大解析核心。

st.set_page_config(page_title="賽馬智腦 V1.69", layout="wide")

# --- 核心數據 (2024/25) ---
REAL_STATS = {
    "jockey": { "Z Purton": 22.9, "J McDonald": 21.3, "M Barzalona": 16.7, "J Moreira": 16.1, "C Williams": 14.8, "H Bowman": 14.5, "K Teetan": 12.0, "C Y Ho": 11.5, "A Badel": 8.5, "A Atzeni": 8.2, "L Hewitson": 7.8, "B Avdulla": 7.5, "Y L Chung": 7.2, "C L Chau": 6.8, "K C Leung": 5.5, "M F Poon": 5.2, "H Bentley": 9.5, "L Ferraris": 8.0, "M Chadwick": 6.5, "A Hamelin": 4.5 },
    "trainer": { "J Size": 11.0, "K L Man": 10.9, "K W Lui": 10.0, "D Eustace": 9.8, "C Fownes": 9.7, "P C Ng": 9.5, "F C Lor": 9.2, "D A Hayes": 8.8, "A S Cruz": 8.5, "C S Shum": 8.3, "P F Yiu": 8.0, "D J Hall": 7.8, "M Newnham": 7.5, "W K Mo": 7.2, "J Richards": 6.5, "W Y So": 6.2, "T P Yung": 5.5, "Y S Tsui": 4.5, "C H Yip": 4.0, "C W Chang": 3.5 }
}
NAME_MAPPING = { "麥道朗": "J McDonald", "潘頓": "Z Purton", "布文": "H Bowman", "艾道拿": "B Avdulla", "金誠剛": "M Barzalona", "希威森": "L Hewitson", "鍾易禮": "Y L Chung", "田泰安": "K Teetan", "周俊樂": "C L Chau", "杜苑欣": "H Doyle", "蔡約翰": "J Size", "伍鵬志": "P C Ng", "方嘉柏": "C Fownes", "大衛希斯": "D A Hayes", "黎昭昇": "J Richards", "鄭俊偉": "C W Chang", "蘇偉賢": "W Y So", "告東尼": "A S Cruz", "徐雨石": "Y S Tsui", "葉楚航": "C H Yip", "丁冠豪": "K H Ting", "文家良": "K L Man" }

# --- AI 計算 ---
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

# --- [特訓版] 精準解析器 ---
def parse_trained_card(text):
    data = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        parts = re.split(r'\s+', line)
        if not parts[0].isdigit(): continue
        try:
            row = {}
            row['馬號'] = int(parts[0])
            idx_name = 1
            while idx_name < len(parts) and not parts[idx_name].strip(): idx_name += 1
            row['馬名'] = parts[idx_name]
            
            idx_wt = idx_name + 1
            while idx_wt < len(parts):
                if parts[idx_wt].isdigit() and 100 <= int(parts[idx_wt]) <= 135:
                    row['負磅'] = int(parts[idx_wt])
                    break
                idx_wt += 1
            
            jockey_part = parts[idx_wt + 1]
            if len(parts) > idx_wt + 2 and "(-" in parts[idx_wt + 2]:
                jockey_part += " " + parts[idx_wt + 2]
                idx_draw = idx_wt + 3
            else:
                idx_draw = idx_wt + 2
                
            row['騎師'] = jockey_part
            if len(parts) > idx_draw and parts[idx_draw].isdigit():
                row['檔位'] = int(parts[idx_draw])
            if len(parts) > idx_draw + 1:
                row['練馬師'] = parts[idx_draw + 1]
            
            data.append(row)
        except: continue
    return pd.DataFrame(data)

def parse_odds_universal(text):
    odds_map = {}
    lines = text.strip().split('\n')
    for line in lines:
        nums = re.findall(r'\d+\.\d+|\d+', line)
        if len(nums) >= 2:
            try:
                h_no = int(nums[0])
                h_win = None
                for n in reversed(nums):
                    if '.' in n: 
                        h_win = float(n)
                        break
                if h_win and 1 <= h_no <= 14: odds_map[h_no] = h_win
            except: pass
    return odds_map

# --- Session ---
if 'race_data' not in st.session_state: st.session_state['race_data'] = None
if 'last_update' not in st.session_state: st.session_state['last_update'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
# [新增] 用於儲存日期場次
if 'race_info' not in st.session_state: st.session_state['race_info'] = {"date": datetime.now().strftime("%Y-%m-%d"), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.69")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入") and pwd == "jay123":
            st.session_state['admin_logged_in'] = True
            st.rerun()
    else:
        # [加回] 1. 賽事資訊設定
        st.subheader("1. 賽事設定")
        c_date, c_race = st.columns(2)
        with c_date: 
            # 讀取上次設定的值
            d_val = datetime.strptime(st.session_state['race_info']['date'], "%Y-%m-%d").date()
            input_date = st.date_input("日期", value=d_val)
        with c_race: 
            input_race = st.number_input("場次", 1, 14, st.session_state['race_info']['no'])
            
        st.divider()
        st.subheader("2. 資料輸入")
        c1, c2 = st.columns(2)
        with c1: card_in = st.text_area("排位表 (特訓格式)", height=300)
        with c2: odds_in = st.text_area("賠率 (任意格式)", height=300)
            
        if st.button("🚀 發布並更新", type="primary"):
            df = parse_trained_card(card_in)
            if not df.empty:
                if odds_in:
                    odds_map = parse_odds_universal(odds_in)
                    df['獨贏'] = df['馬號'].map(odds_map).fillna("-")
                else: df['獨贏'] = "-"
                
                scores = []
                for _, row in df.iterrows(): scores.append(calculate_ai_score(row))
                df['AI分數'] = scores
                total = sum(scores)
                df['勝率%'] = (df['AI分數']/total*100).round(1) if total>0 else 0.0
                
                st.session_state['race_data'] = df
                # [加回] 儲存日期場次
                st.session_state['race_info'] = {"date": str(input_date), "no": input_race}
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
                st.success(f"已發布 {input_date} 第 {input_race} 場賽事！")
            else: st.error("解析失敗")

else:
    # --- 前台顯示 ---
    if st.session_state['race_data'] is None: 
        st.info("👋 歡迎！請等待管理員發布資料。")
    else:
        # 讀取資訊
        info = st.session_state['race_info']
        st.title(f"📊 {info['date']} (第 {info['no']} 場)")
        
        df = st.session_state['race_data'].copy()
        df = df.sort_values('勝率%', ascending=False).reset_index(drop=True)
        
        # Top 4 Cards
        top4 = df.head(4)
        cols = st.columns(4)
        for i, col in enumerate(cols):
            if i < len(top4):
                h = top4.iloc[i]
                col.metric(f"#{h['馬號']} {h['馬名']}", f"{h['勝率%']}%", f"賠率: {h['獨贏']}")
        
        st.divider()
        
        # [加回] 明確顯示獨贏欄位
        # 確保顯示的欄位都在 DataFrame 中
        target_cols = ['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅']
        display_cols = [c for c in target_cols if c in df.columns]
        
        st.dataframe(
            df[display_cols],
            column_config={
                "勝率%": st.column_config.ProgressColumn("AI 勝率", format="%.1f%%", min_value=0, max_value=100),
                "獨贏": st.column_config.TextColumn("獨贏賠率", help="即時賠率"),
                "馬號": st.column_config.NumberColumn("No.", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"最後更新: {st.session_state['last_update']}")
