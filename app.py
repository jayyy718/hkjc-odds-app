import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.71 (Absolute Row Indexing Fix) =====================
# 修復重點：解決整數賠率 (e.g. 11, 22) 被漏抓，導致錯抓位置賠率的問題。
# 新邏輯：不依賴小數點特徵，改用「相對行數位置」鎖定。
# 規則：馬號出現後的「第二個非空行」即為獨贏賠率。

st.set_page_config(page_title="賽馬智腦 V1.71", layout="wide")

# --- 核心數據 (不變) ---
REAL_STATS = {
    "jockey": { "Z Purton": 22.9, "J McDonald": 21.3, "M Barzalona": 16.7, "J Moreira": 16.1, "C Williams": 14.8, "H Bowman": 14.5, "K Teetan": 12.0, "C Y Ho": 11.5, "A Badel": 8.5, "A Atzeni": 8.2, "L Hewitson": 7.8, "B Avdulla": 7.5, "Y L Chung": 7.2, "C L Chau": 6.8, "K C Leung": 5.5, "M F Poon": 5.2, "H Bentley": 9.5, "L Ferraris": 8.0, "M Chadwick": 6.5, "A Hamelin": 4.5 },
    "trainer": { "J Size": 11.0, "K L Man": 10.9, "K W Lui": 10.0, "D Eustace": 9.8, "C Fownes": 9.7, "P C Ng": 9.5, "F C Lor": 9.2, "D A Hayes": 8.8, "A S Cruz": 8.5, "C S Shum": 8.3, "P F Yiu": 8.0, "D J Hall": 7.8, "M Newnham": 7.5, "W K Mo": 7.2, "J Richards": 6.5, "W Y So": 6.2, "T P Yung": 5.5, "Y S Tsui": 4.5, "C H Yip": 4.0, "C W Chang": 3.5 }
}
NAME_MAPPING = { "麥道朗": "J McDonald", "潘頓": "Z Purton", "布文": "H Bowman", "艾道拿": "B Avdulla", "金誠剛": "M Barzalona", "希威森": "L Hewitson", "鍾易禮": "Y L Chung", "田泰安": "K Teetan", "周俊樂": "C L Chau", "杜苑欣": "H Doyle", "蔡約翰": "J Size", "伍鵬志": "P C Ng", "方嘉柏": "C Fownes", "大衛希斯": "D A Hayes", "黎昭昇": "J Richards", "鄭俊偉": "C W Chang", "蘇偉賢": "W Y So", "告東尼": "A S Cruz", "徐雨石": "Y S Tsui", "葉楚航": "C H Yip", "丁冠豪": "K H Ting", "文家良": "K L Man", "潘大衛": "D Egan", "奧爾民": "J Orman" }

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

# --- 排位解析器 (維持 V1.68) ---
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

# --- [修正] 絕對行數索引賠率解析器 ---
def parse_odds_strict_sequence(text):
    """
    針對格式：
    Line 1: 馬號 (1)
    Line 2: 馬名資訊...
    Line 3: 獨贏 (6.2)  <-- 抓這個
    Line 4: 位置 (2.4)
    Line 5: 馬號 (2)
    ...
    """
    odds_map = {}
    
    # 1. 將文字按行分割，並去除空行
    raw_lines = text.split('\n')
    lines = [line.strip() for line in raw_lines if line.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 檢測是否為馬號 (1-14 的純數字)
        if line.isdigit() and 1 <= int(line) <= 14:
            current_horse = int(line)
            
            # 根據您的格式，馬號下面是資訊，再下面才是獨贏
            # Index i = 馬號
            # Index i+1 = 馬名資訊
            # Index i+2 = 獨贏 <--- 目標
            
            if i + 2 < len(lines):
                win_line = lines[i+2]
                
                # 嘗試提取賠率 (支援整數和小數)
                try:
                    # 有時候賠率可能會帶有其他字元，嘗試提取第一個數字
                    nums = re.findall(r'\d+\.\d+|\d+', win_line)
                    if nums:
                        val = float(nums[0])
                        # 簡單過濾：獨贏通常不會超過 500
                        if val < 500:
                            odds_map[current_horse] = val
                except:
                    pass
            
            # 跳過這匹馬的區塊，尋找下一個馬號
            # 因為一個區塊至少有 4 行 (號, 名, 贏, 位)，所以我們可以安全地跳過幾行加速
            i += 2 
        else:
            i += 1
            
    return odds_map

# --- Session ---
if 'race_data' not in st.session_state: st.session_state['race_data'] = None
if 'last_update' not in st.session_state: st.session_state['last_update'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
if 'race_info' not in st.session_state: st.session_state['race_info'] = {"date": datetime.now().strftime("%Y-%m-%d"), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.71")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入") and pwd == "jay123":
            st.session_state['admin_logged_in'] = True
            st.rerun()
    else:
        st.subheader("1. 賽事設定")
        c_d, c_r = st.columns(2)
        with c_d: 
            d_val = datetime.strptime(st.session_state['race_info']['date'], "%Y-%m-%d").date()
            input_date = st.date_input("日期", value=d_val)
        with c_r: 
            input_race = st.number_input("場次", 1, 14, st.session_state['race_info']['no'])
            
        st.divider()
        st.subheader("2. 資料輸入")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.info("排位表 (特訓格式)")
            card_in = st.text_area("排位文字", height=300)
        with c2: 
            st.info("賠率 (嚴格順序格式)")
            st.caption("請確保順序：馬號 -> 資訊 -> 獨贏 -> 位置")
            odds_in = st.text_area("賠率文字", height=300)
            
        if st.button("🚀 發布並更新", type="primary"):
            df = parse_trained_card(card_in)
            if not df.empty:
                if odds_in:
                    # 使用新的嚴格順序解析器
                    odds_map = parse_odds_strict_sequence(odds_in)
                    df['獨贏'] = df['馬號'].map(odds_map).fillna("-")
                else: df['獨贏'] = "-"
                
                scores = []
                for _, row in df.iterrows(): scores.append(calculate_ai_score(row))
                df['AI分數'] = scores
                total = sum(scores)
                df['勝率%'] = (df['AI分數']/total*100).round(1) if total>0 else 0.0
                
                st.session_state['race_data'] = df
                st.session_state['race_info'] = {"date": str(input_date), "no": input_race}
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
                
                st.success(f"已發布！共 {len(df)} 匹馬，解析到 {len(odds_map) if odds_in else 0} 筆賠率。")
                
                # Debug 顯示解析到的賠率，讓您確認
                if odds_in:
                    st.write("解析到的賠率預覽:", odds_map)
                    
            else: st.error("排位表解析失敗")

else:
    if st.session_state['race_data'] is None: st.info("等待資料...")
    else:
        info = st.session_state['race_info']
        st.title(f"📊 {info['date']} (第 {info['no']} 場)")
        
        df = st.session_state['race_data'].copy()
        df = df.sort_values('勝率%', ascending=False).reset_index(drop=True)
        
        top4 = df.head(4)
        cols = st.columns(4)
        for i, col in enumerate(cols):
            if i < len(top4):
                h = top4.iloc[i]
                col.metric(f"#{h['馬號']} {h['馬名']}", f"{h['勝率%']}%", f"賠率: {h['獨贏']}")
        
        st.divider()
        
        display_cols = [c for c in ['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅'] if c in df.columns]
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
        st.caption(f"最後更新: {st.session_state['last_update']}")
