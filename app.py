import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.68 (Sample-Trained Parser) =====================
# 特訓目標：完美解析用戶提供的真實排位表樣本
# 樣本特徵：馬號 [tab] 馬名 [編號] [負磅] [騎師] [檔位] [練馬師] [評分...]

st.set_page_config(page_title="賽馬智腦 V1.68", layout="wide")

# --- 數據庫與映射 (不變) ---
REAL_STATS = {
    "jockey": { "Z Purton": 22.9, "J McDonald": 21.3, "M Barzalona": 16.7, "J Moreira": 16.1, "C Williams": 14.8, "H Bowman": 14.5, "K Teetan": 12.0, "C Y Ho": 11.5, "A Badel": 8.5, "A Atzeni": 8.2, "L Hewitson": 7.8, "B Avdulla": 7.5, "Y L Chung": 7.2, "C L Chau": 6.8, "K C Leung": 5.5, "M F Poon": 5.2, "H Bentley": 9.5, "L Ferraris": 8.0, "M Chadwick": 6.5, "A Hamelin": 4.5 },
    "trainer": { "J Size": 11.0, "K L Man": 10.9, "K W Lui": 10.0, "D Eustace": 9.8, "C Fownes": 9.7, "P C Ng": 9.5, "F C Lor": 9.2, "D A Hayes": 8.8, "A S Cruz": 8.5, "C S Shum": 8.3, "P F Yiu": 8.0, "D J Hall": 7.8, "M Newnham": 7.5, "W K Mo": 7.2, "J Richards": 6.5, "W Y So": 6.2, "T P Yung": 5.5, "Y S Tsui": 4.5, "C H Yip": 4.0, "C W Chang": 3.5 }
}
NAME_MAPPING = { "麥道朗": "J McDonald", "潘頓": "Z Purton", "潘大衛": "D Egan", "布文": "H Bowman", "艾道拿": "B Avdulla", "金誠剛": "M Barzalona", "希威森": "L Hewitson", "鍾易禮": "Y L Chung", "奧爾民": "J Orman", "田泰安": "K Teetan", "周俊樂": "C L Chau", "杜苑欣": "H Doyle", "蔡約翰": "J Size", "伍鵬志": "P C Ng", "方嘉柏": "C Fownes", "大衛希斯": "D A Hayes", "黎昭昇": "J Richards", "鄭俊偉": "C W Chang", "蘇偉賢": "W Y So", "告東尼": "A S Cruz", "徐雨石": "Y S Tsui", "葉楚航": "C H Yip", "丁冠豪": "K H Ting", "文家良": "K L Man" }

# --- AI 計算 ---
def calculate_ai_score(row):
    score = 0
    try:
        odds = float(row['獨贏'])
        if odds > 0: score += ((1 / odds) * 100) * 0.7 
    except: pass
        
    j_name = re.sub(r'\s*\([+-]?\d+\)', '', str(row.get('騎師', ''))).strip() # 去掉 (-2)
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
        
        # 1. 切割 (處理 tab 和多重空格)
        parts = re.split(r'\s+', line)
        
        # 2. 驗證: 第一個必須是數字 (馬號)
        if not parts[0].isdigit(): continue
        
        try:
            # 根據您的樣本:
            # 1 (馬號) 幸運同行 (馬名) J331 (編號) 135 (負磅) 麥道朗 (騎師) 5 (檔位) 蔡約翰 (練馬師) ...
            
            row = {}
            row['馬號'] = int(parts[0])
            
            # 馬名通常在第二欄，且是中文
            # 有時候會有「綵衣」是空的，所以馬名可能在 index 1
            idx_name = 1
            # 簡單檢查：如果 parts[1] 是空的，往後找
            while idx_name < len(parts) and not parts[idx_name].strip():
                idx_name += 1
            row['馬名'] = parts[idx_name]
            
            # 負磅：在馬名後面找 110-135 的數字
            # 編號 (J331) 在馬名和負磅中間
            idx_wt = idx_name + 1
            while idx_wt < len(parts):
                if parts[idx_wt].isdigit() and 100 <= int(parts[idx_wt]) <= 135:
                    row['負磅'] = int(parts[idx_wt])
                    break
                idx_wt += 1
                
            # 騎師：負磅後面那個就是騎師 (可能是 "麥道朗" 或 "鍾易禮 (-2)")
            # 這裡要注意，如果有 (-2)，它可能會被 split 切開
            # 所以我們要看 idx_wt + 1
            
            jockey_part = parts[idx_wt + 1]
            if "(-" in parts[idx_wt + 2]: # 處理 (-2) 分開的情況
                jockey_part += " " + parts[idx_wt + 2]
                idx_draw = idx_wt + 3
            else:
                idx_draw = idx_wt + 2
                
            row['騎師'] = jockey_part
            
            # 檔位：騎師後面那個小數字 (1-14)
            if parts[idx_draw].isdigit():
                row['檔位'] = int(parts[idx_draw])
            
            # 練馬師：檔位後面
            row['練馬師'] = parts[idx_draw + 1]
            
            data.append(row)
            
        except Exception as e:
            # 為了除錯，如果哪一行失敗了可以看
            # print(f"Error parsing line: {line} -> {e}")
            continue
            
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
if 'race_info' not in st.session_state: st.session_state['race_info'] = {"date": datetime.now().strftime("%Y-%m-%d"), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.68")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入") and pwd == "jay123":
            st.session_state['admin_logged_in'] = True
            st.rerun()
    else:
        st.info("💡 提示：請直接將您剛剛提供的排位表格式貼在左側。")
        c1, c2 = st.columns(2)
        with c1: card_in = st.text_area("排位表", height=300)
        with c2: odds_in = st.text_area("賠率", height=300)
            
        if st.button("🚀 發布", type="primary"):
            df = parse_trained_card(card_in)
            if not df.empty:
                st.success(f"成功識別 {len(df)} 匹馬 (1號: {df.iloc[0]['馬名']}, 檔位: {df.iloc[0]['檔位']})")
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
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
            else: st.error("解析失敗")

else:
    if st.session_state['race_data'] is None: st.info("等待資料...")
    else:
        df = st.session_state['race_data'].copy()
        df = df.sort_values('勝率%', ascending=False).reset_index(drop=True)
        
        top4 = df.head(4)
        cols = st.columns(4)
        for i, col in enumerate(cols):
            if i < len(top4):
                h = top4.iloc[i]
                col.metric(f"#{h['馬號']} {h['馬名']}", f"{h['勝率%']}%", f"賠率: {h['獨贏']}")
        
        st.dataframe(
            df[['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅']],
            column_config={"勝率%": st.column_config.ProgressColumn("AI 勝率", format="%.1f%%", min_value=0, max_value=100)},
            use_container_width=True, hide_index=True
        )
