import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ===================== V1.72 (Final Format Customization) =====================
# 特色：針對用戶最終提供的排位表格式進行精準定制
# 新格式：馬匹編號 6次近績 綵衣 馬名 負磅 騎師 檔位 ...

st.set_page_config(page_title="賽馬智腦 V1.72", layout="wide")

# --- 核心數據與映射 (不變) ---
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

# --- [V1.72 核心] 最終版排位解析器 ---
def parse_card_v172(text):
    """
    針對格式：馬號 6次近績 [空] 馬名 負磅 騎師 檔位 練馬師...
    """
    data = []
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line or "馬匹編號" in line: continue

        # 使用正則表達式，更準確地處理多個空格或 tab
        parts = re.split(r'\s+', line)
        if not parts[0].isdigit(): continue

        try:
            row = {}
            # --- 根據新格式的固定索引 ---
            row['馬號'] = int(parts[0])
            row['6次近績'] = parts[1]
            row['馬名'] = parts[2]
            row['負磅'] = int(parts[3])

            # --- 浮動索引處理 (騎師+/-) ---
            # 騎師可能佔用 1 或 2 個位置
            current_index = 4
            jockey_part = parts[current_index]
            current_index += 1
            if current_index < len(parts) and "(-" in parts[current_index]:
                jockey_part += " " + parts[current_index]
                current_index += 1
            row['騎師'] = jockey_part

            # 騎師後面的就是檔位
            if current_index < len(parts) and parts[current_index].isdigit():
                row['檔位'] = int(parts[current_index])
                current_index += 1

            # 檔位後面的就是練馬師
            if current_index < len(parts):
                row['練馬師'] = parts[current_index]
                current_index += 1
            
            # 練馬師後面的就是評分
            if current_index < len(parts):
                row['評分'] = parts[current_index]

            data.append(row)

        except Exception:
            continue
            
    return pd.DataFrame(data)

# --- 賠率解析器 (維持不變) ---
def parse_odds_strict_sequence(text):
    odds_map = {}
    raw_lines = text.split('\n')
    lines = [line.strip() for line in raw_lines if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.isdigit() and 1 <= int(line) <= 14:
            current_horse = int(line)
            if i + 2 < len(lines):
                win_line = lines[i+2]
                try:
                    nums = re.findall(r'\d+\.\d+|\d+', win_line)
                    if nums:
                        odds_map[current_horse] = float(nums[0])
                except: pass
            i += 2 
        else: i += 1
    return odds_map

# --- Session ---
if 'race_data' not in st.session_state: st.session_state['race_data'] = None
if 'last_update' not in st.session_state: st.session_state['last_update'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False
if 'race_info' not in st.session_state: st.session_state['race_info'] = {"date": datetime.now().strftime("%Y-%m-%d"), "no": 1}

# ===================== UI =====================
st.sidebar.title("🏇 賽馬智腦 V1.72")
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
            st.info("排位表 (最終版格式)")
            card_in = st.text_area("排位文字", height=300)
        with c2: 
            st.info("賠率 (垂直格式)")
            odds_in = st.text_area("賠率文字", height=300)
            
        if st.button("🚀 發布", type="primary"):
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
                
                st.session_state['race_data'] = df
                st.session_state['race_info'] = {"date": str(input_date), "no": input_race}
                st.session_state['last_update'] = pd.Timestamp.now().strftime("%H:%M:%S")
                
                st.success(f"發布成功！共 {len(df)} 匹馬。")
                # 為了讓您確認，顯示解析後的第一行數據
                st.write("解析預覽:", df.head(1).to_dict('records')[0])
                    
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
        
        # 新增「6次近績」到顯示欄位
        display_cols = [c for c in ['馬號', '馬名', '勝率%', '獨贏', '騎師', '練馬師', '檔位', '負磅', '評分', '6次近績'] if c in df.columns]
        
        st.dataframe(
            df[display_cols],
            column_config={
                "勝率%": st.column_config.ProgressColumn("AI 勝率", format="%.1f%%", min_value=0, max_value=100),
                "獨贏": st.column_config.TextColumn("獨贏賠率"),
                "6次近績": st.column_config.TextColumn("近績"),
            },
            use_container_width=True,
            hide_index=True
        )
        st.caption(f"最後更新: {st.session_state['last_update']}")
