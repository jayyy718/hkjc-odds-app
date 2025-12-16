import streamlit as st
import pandas as pd
import numpy as np
import re
import os

# ===================== V1.63 (Big Data AI Edition) =====================
# 1. 整合 2024-2025 賽季原始數據 (CSV)
# 2. 計算真實騎練勝率與檔位優勢
# 3. 智能中英對照映射

st.set_page_config(page_title="賽馬智腦 V1.63", layout="wide")

# --- 設定：中英翻譯字典 (將中文輸入映射到英文 CSV 數據) ---
# 這是連接「用戶貼上的中文」與「CSV 裡的英文」的橋樑
NAME_MAPPING = {
    # 騎師
    "潘頓": "Z Purton", "布文": "H Bowman", "麥道朗": "J McDonald", 
    "田泰安": "K Teetan", "何澤堯": "C Y Ho", "艾道拿": "B Avdulla",
    "鍾易禮": "Y L Chung", "希威森": "L Hewitson", "梁家俊": "K C Leung",
    "班德禮": "H Bentley", "霍宏聲": "L Ferraris", "蔡明紹": "M Chadwick",
    "周俊樂": "C L Chau", "艾兆禮": "A Atzeni", "楊明綸": "M L Yeung",
    "巴度": "A Badel", "賀銘年": "A Hamelin", "潘明輝": "M F Poon",
    "巫顯東": "H T Mo", "黃智弘": "E C W Wong", "莫雷拉": "J Moreira",
    
    # 練馬師
    "伍鵬志": "P C Ng", "呂健威": "K W Lui", "姚本輝": "P F Yiu",
    "蔡約翰": "J Size", "沈集成": "C S Shum", "告東尼": "A S Cruz",
    "大衛希斯": "D A Hayes", "希斯": "D A Hayes", "方嘉柏": "C Fownes",
    "羅富全": "F C Lor", "賀賢": "D J Hall", "韋達": "D J Whyte",
    "黎昭昇": "J Richards", "廖康銘": "M Newnham", "蘇偉賢": "W Y So",
    "葉楚航": "C H Yip", "鄭俊偉": "C W Chang", "徐雨石": "Y S Tsui",
    "文家良": "K L Man", "巫偉傑": "W K Mo", "容天鵬": "T P Yung"
}

# --- 核心：數據庫載入與分析 ---
@st.cache_data
def load_and_analyze_data():
    """
    讀取 CSV 並計算騎師、練馬師的勝率統計數據
    """
    stats = {
        "jockey_win_rate": {},
        "trainer_win_rate": {},
        "draw_stats": {},
        "data_loaded": False
    }
    
    file_path = "20242025HongKongHorseRacingRawData.csv"
    
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            
            # 清理排名數據 (將 '1 DH', '1' 轉為 1)
            def clean_pla(x):
                try:
                    return int(re.sub(r'\D', '', str(x)))
                except:
                    return 99
            
            df['Rank'] = df['Pla.'].apply(clean_pla)
            
            # 1. 計算騎師勝率
            # 只看前 4 名的表現來給分
            jockey_groups = df.groupby('Jockey')['Rank']
            for name, ranks in jockey_groups:
                total = len(ranks)
                wins = sum(ranks == 1)
                places = sum(ranks <= 3)
                if total > 5: # 至少跑過 5 場才統計
                    stats["jockey_win_rate"][name] = (wins / total) * 100
            
            # 2. 計算練馬師勝率
            trainer_groups = df.groupby('Trainer')['Rank']
            for name, ranks in trainer_groups:
                total = len(ranks)
                wins = sum(ranks == 1)
                if total > 5:
                    stats["trainer_win_rate"][name] = (wins / total) * 100
            
            stats["data_loaded"] = True
            stats["total_races"] = len(df)
            
        except Exception as e:
            st.error(f"數據載入錯誤: {e}")
    else:
        # 如果找不到檔案，不報錯，只是標記未載入
        pass
        
    return stats

# 初始化數據庫
DB_STATS = load_and_analyze_data()

# --- AI 計算引擎 (結合歷史數據) ---
def calculate_ai_score_v2(row, db_stats):
    score = 0
    details = []
    
    # 1. 賠率權重 (市場信心) - 基礎分 0-60 分
    try:
        odds = float(row['獨贏'])
        if odds > 0:
            # 賠率越低分越高: 2.0賠率 -> 50%機率 -> 30分
            implied_prob = (1 / odds) * 100
            odds_score = implied_prob * 0.6
            score += odds_score
    except:
        pass
        
    # 如果有歷史數據庫，使用真實數據加成
    if db_stats["data_loaded"]:
        
        # 2. 騎師數據 (中英對照)
        jockey_zh = str(row.get('騎師', '')).strip()
        jockey_en = NAME_MAPPING.get(jockey_zh, "")
        
        # 嘗試模糊匹配 (如果字典沒找到)
        if not jockey_en:
            # 簡單處理：如果是英文輸入就直接用
            if re.search(r'[a-zA-Z]', jockey_zh): jockey_en = jockey_zh
        
        if jockey_en in db_stats["jockey_win_rate"]:
            win_rate = db_stats["jockey_win_rate"][jockey_en]
            # 勝率加成：每 1% 勝率 + 0.5 分
            # 例如潘頓勝率 20% -> +10 分
            j_score = win_rate * 0.5
            score += j_score
            details.append(f"騎師{int(win_rate)}%")
        
        # 3. 練馬師數據
        trainer_zh = str(row.get('練馬師', '')).strip()
        trainer_en = NAME_MAPPING.get(trainer_zh, "")
        
        if trainer_en in db_stats["trainer_win_rate"]:
            t_win_rate = db_stats["trainer_win_rate"][trainer_en]
            t_score = t_win_rate * 0.5
            score += t_score
            details.append(f"練馬師{int(t_win_rate)}%")
            
    else:
        # 降級模式：如果沒有 CSV，使用簡單規則
        if "潘頓" in str(row.get('騎師', '')): score += 5
    
    # 4. 檔位優勢 (通用規則)
    try:
        draw = int(row['檔位'])
        if draw <= 3: score += 4
        elif draw >= 11: score -= 2
    except: pass
    
    return score

# --- 排位與賠率解析 (V1.61) ---
def parse_strict_card(text):
    data = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or "馬號" in line: continue
        parts = line.split()
        if len(parts) < 7 or not parts[0].isdigit(): continue
        try:
            row = {
                '馬號': int(parts[0]),
                '馬名': parts[1],
                '負磅': parts[2],
                '騎師': parts[4],
                '檔位': int(parts[5]),
                '練馬師': parts[6],
                '評分': parts[8] if len(parts) > 8 else "-"
            }
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

# --- Session State 初始化 ---
if 'race_data' not in st.session_state: st.session_state['race_data'] = None
if 'last_update' not in st.session_state: st.session_state['last_update'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False

# ===================== 介面邏輯 =====================

st.sidebar.title("🏇 賽馬智腦 V1.63")
page = st.sidebar.radio("選單", ["📊 賽事看板", "🔒 後台管理"])

if page == "🔒 後台管理":
    st.header("🔒 管理員")
    
    if not st.session_state['admin_logged_in']:
        pwd = st.text_input("密碼", type="password")
        if st.button("登入"):
            if pwd == "jay123":
                st.session_state['admin_logged_in'] = True
                st.rerun()
            else:
                st.error("密碼錯誤")
    else:
        # 資料庫狀態
        if DB_STATS["data_loaded"]:
            st.success(f"📚 歷史數據庫已連線 (包含 {DB_STATS['total_races']} 場賽事記錄)")
        else:
            st.warning("⚠️ 未偵測到 CSV 數據檔，系統將使用簡易模式運行。")

        c1, c2 = st.columns(2)
        with c1:
            st.info("1. 排位表")
            card_text = st.text_area("格式: 馬號 馬名 負磅 +/- 騎師 檔位...", height=300)
        with c2:
            st.info("2. 即時賠率")
            odds_text = st.text_area("格式: 馬號 賠率", height=300)
            
        if st.button("🚀 計算並發布", type="primary"):
            df = parse_strict_card(card_text)
            if not df.empty:
                if odds_text:
                    odds_map = parse_odds_universal(odds_text)
                    df['獨贏'] = df['馬號'].map(odds_map).fillna("-")
                else:
                    df['獨贏'] = "-"
                
                # 計算 AI 分數
                scores = []
                for _, row in df.iterrows():
                    scores.append(calculate_ai_score_v2(row, DB_STATS))
                
                df['AI分數'] = scores
                # 正規化勝率
                total_score = sum(scores)
                if total_score > 0:
                    df['勝率%'] = (df['AI分數'] / total_score * 100).round(1)
                else:
                    df['勝率%'] = 0.0
                
                st.session_state['race_data'] = df
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
                st.success(f"發布成功！")
            else:
                st.error("解析失敗")

else:
    st.title("📊 賽馬智腦分析看板")
    
    if st.session_state['race_data'] is None:
        st.info("等待資料發布...")
    else:
        df = st.session_state['race_data'].copy()
        
        # 顯示大數據加成標籤
        if DB_STATS["data_loaded"]:
            st.caption("✅ AI 已啟用大數據引擎：結合 2024/25 賽季真實騎練勝率計算")
        
        # 排序
        df = df.sort_values('勝率%', ascending=False).reset_index(drop=True)
        
        # 卡片視圖
        top4 = df.head(4)
        cols = st.columns(4)
        for i, col in enumerate(cols):
            if i < len(top4):
                h = top4.iloc[i]
                col.metric(
                    label=f"No.{h['馬號']} {h['馬名']}",
                    value=f"{h['勝率%']}%",
                    delta=f"賠率: {h['獨贏']}"
                )
        
        st.divider()
        st.dataframe(
            df[['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位']],
            column_config={
                "勝率%": st.column_config.ProgressColumn("AI 預測勝率", format="%.1f%%", min_value=0, max_value=100),
                "獨贏": st.column_config.TextColumn("賠率"),
            },
            use_container_width=True,
            hide_index=True
        )
