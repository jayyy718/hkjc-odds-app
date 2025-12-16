import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta

# ===================== V1.66 (Ultimate Format Edition) =====================
# 特色：針對特定格式 [馬號, 綵衣, 馬名, 烙號, 負磅, 騎師, 檔位, 練馬師...] 進行精準解析

st.set_page_config(page_title="賽馬智腦 V1.66", layout="wide")

# --- 核心數據庫 (2024/25) ---
REAL_STATS = {
    "jockey": {
        "Z Purton": 22.9, "J McDonald": 21.3, "M Barzalona": 16.7, "J Moreira": 16.1, 
        "C Williams": 14.8, "H Bowman": 14.5, "K Teetan": 12.0, "C Y Ho": 11.5,
        "A Badel": 8.5, "A Atzeni": 8.2, "L Hewitson": 7.8, "B Avdulla": 7.5,
        "Y L Chung": 7.2, "C L Chau": 6.8, "K C Leung": 5.5, "M F Poon": 5.2,
        "H Bentley": 9.5, "L Ferraris": 8.0, "M Chadwick": 6.5, "A Hamelin": 4.5
    },
    "trainer": {
        "J Size": 11.0, "K L Man": 10.9, "K W Lui": 10.0, "D Eustace": 9.8,
        "C Fownes": 9.7, "P C Ng": 9.5, "F C Lor": 9.2, "D A Hayes": 8.8,
        "A S Cruz": 8.5, "C S Shum": 8.3, "P F Yiu": 8.0, "D J Hall": 7.8,
        "M Newnham": 7.5, "W K Mo": 7.2, "J Richards": 6.5, "W Y So": 6.2,
        "T P Yung": 5.5, "Y S Tsui": 4.5, "C H Yip": 4.0, "C W Chang": 3.5
    }
}

# --- 中英對照 ---
NAME_MAPPING = {
    "潘頓": "Z Purton", "布文": "H Bowman", "麥道朗": "J McDonald", 
    "田泰安": "K Teetan", "何澤堯": "C Y Ho", "艾道拿": "B Avdulla",
    "鍾易禮": "Y L Chung", "希威森": "L Hewitson", "梁家俊": "K C Leung",
    "班德禮": "H Bentley", "霍宏聲": "L Ferraris", "蔡明紹": "M Chadwick",
    "周俊樂": "C L Chau", "艾兆禮": "A Atzeni", "楊明綸": "M L Yeung",
    "巴度": "A Badel", "賀銘年": "A Hamelin", "潘明輝": "M F Poon",
    "莫雷拉": "J Moreira", "巴米高": "M Barzalona", "韋紀力": "C Williams",
    "伍鵬志": "P C Ng", "呂健威": "K W Lui", "姚本輝": "P F Yiu",
    "蔡約翰": "J Size", "沈集成": "C S Shum", "告東尼": "A S Cruz",
    "大衛希斯": "D A Hayes", "希斯": "D A Hayes", "方嘉柏": "C Fownes",
    "羅富全": "F C Lor", "賀賢": "D J Hall", "韋達": "D J Whyte",
    "黎昭昇": "J Richards", "廖康銘": "M Newnham", "蘇偉賢": "W Y So",
    "葉楚航": "C H Yip", "鄭俊偉": "C W Chang", "徐雨石": "Y S Tsui",
    "文家良": "K L Man", "巫偉傑": "W K Mo", "容天鵬": "T P Yung",
    "游達榮": "D Eustace"
}

# --- AI 計算引擎 ---
def calculate_ai_score(row):
    score = 0
    # 1. 賠率
    try:
        odds = float(row['獨贏'])
        if odds > 0:
            implied_prob = (1 / odds) * 100
            score += implied_prob * 0.7 
    except: pass
        
    # 2. 騎師
    jockey_zh = str(row.get('騎師', '')).strip()
    jockey_en = NAME_MAPPING.get(jockey_zh, "")
    if not jockey_en and re.search(r'[a-zA-Z]', jockey_zh): jockey_en = jockey_zh
    if jockey_en in REAL_STATS["jockey"]:
        score += REAL_STATS["jockey"][jockey_en] * 0.6
        
    # 3. 練馬師
    trainer_zh = str(row.get('練馬師', '')).strip()
    trainer_en = NAME_MAPPING.get(trainer_zh, "")
    if trainer_en in REAL_STATS["trainer"]:
        score += REAL_STATS["trainer"][trainer_en] * 0.4
    
    # 4. 檔位
    try:
        draw = int(row['檔位'])
        if draw <= 3: score += 5
        elif draw >= 11: score -= 3
    except: pass
    
    return score

# --- 精準排位解析器 (V1.66) ---
def parse_card_v166(text):
    """
    格式: 馬號(0) 綵衣(1) 馬名(2) 烙號(3) 負磅(4) 騎師(5) 檔位(6) 練馬師(7) 評分(8) ...
    """
    data = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or "馬匹編號" in line: continue # 跳過標題
        
        parts = line.split()
        
        # 至少要有到練馬師的長度 (8欄)
        if len(parts) < 8: continue
        
        # 檢查第一欄是否為數字 (馬號)
        if not parts[0].isdigit(): continue
        
        try:
            # 根據您提供的順序 mapping
            row = {
                '馬號': int(parts[0]),
                '馬名': parts[2], # index 2
                '負磅': parts[4], # index 4
                '騎師': parts[5], # index 5
                '檔位': int(parts[6]), # index 6 (關鍵!)
                '練馬師': parts[7], # index 7
                '評分': parts[8], # index 8
                # '配備': parts[11] if len(parts) > 11 else ""
            }
            data.append(row)
        except:
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

# --- Session 初始化 ---
if 'race_data' not in st.session_state: st.session_state['race_data'] = None
if 'last_update' not in st.session_state: st.session_state['last_update'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
if 'race_info' not in st.session_state: st.session_state['race_info'] = {"date": datetime.now().strftime("%Y-%m-%d"), "no": 1}

# ===================== 介面 =====================

st.sidebar.title("🏇 賽馬智腦 V1.66")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員控制台")
    
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入"):
            if pwd == "jay123":
                st.session_state['admin_logged_in'] = True
                st.rerun()
            else:
                st.error("密碼錯誤")
    else:
        st.success("✅ 系統正常運作中")
        
        st.subheader("1. 賽事資訊")
        c_date, c_race = st.columns(2)
        with c_date:
            input_date = st.date_input("日期")
        with c_race:
            input_race = st.number_input("場次", 1, 14, 1)
            
        st.subheader("2. 資料輸入")
        c1, c2 = st.columns(2)
        with c1:
            st.info("排位表 (指定格式)")
            st.caption("馬號 綵衣 馬名 烙號 負磅 騎師 檔位 練馬師...")
            card_text = st.text_area("排位文字", height=300)
        with c2:
            st.info("即時賠率 (馬會)")
            st.caption("馬號 賠率")
            odds_text = st.text_area("賠率文字", height=300)
            
        if st.button("🚀 發布", type="primary"):
            df = parse_card_v166(card_text)
            if not df.empty:
                if odds_text:
                    odds_map = parse_odds_universal(odds_text)
                    df['獨贏'] = df['馬號'].map(odds_map).fillna("-")
                else:
                    df['獨贏'] = "-"
                
                scores = []
                for _, row in df.iterrows():
                    scores.append(calculate_ai_score(row))
                
                df['AI分數'] = scores
                total_score = sum(scores)
                if total_score > 0:
                    df['勝率%'] = (df['AI分數'] / total_score * 100).round(1)
                else:
                    df['勝率%'] = 0.0
                
                st.session_state['race_data'] = df
                st.session_state['race_info'] = {"date": str(input_date), "no": input_race}
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
                
                st.success(f"已更新！共 {len(df)} 匹馬。")
            else:
                st.error("解析失敗：請確認排位表格式是否正確。")

else:
    if st.session_state['race_data'] is None:
        st.title("📊 賽馬智腦")
        st.info("請等待管理員發布。")
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
                col.metric(
                    label=f"#{h['馬號']} {h['馬名']}",
                    value=f"{h['勝率%']}%",
                    delta=f"賠率: {h['獨贏']}"
                )
        
        st.divider()
        st.dataframe(
            df[['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅', '評分']],
            column_config={
                "勝率%": st.column_config.ProgressColumn("AI 勝率", format="%.1f%%", min_value=0, max_value=100),
                "獨贏": st.column_config.TextColumn("賠率"),
                "馬號": st.column_config.NumberColumn("No.", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
