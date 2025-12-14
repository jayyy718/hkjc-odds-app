import streamlit as st
import pandas as pd
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ===================== 0. 全局數據共享核心 =====================
@st.cache_resource
def get_global_data():
    data = {}
    for i in range(1, 15):
        data[i] = {
            "current_df": pd.DataFrame(),
            "last_df": pd.DataFrame(),
            "last_update": "無數據",
            "raw_odds_text": "",
            "raw_info_text": ""
        }
    return data

race_storage = get_global_data()

# ===================== 1. 頁面配置與 CSS (修復版) =====================
st.set_page_config(page_title="HKJC 賽馬智腦 By Jay", layout="wide")

st.markdown("""
<style>
    /* 全局字體設定 */
    .stApp { 
        background-color: #f5f7f9; 
        color: #333333; 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
    }
    
    /* 側邊欄強制修復：白底深字 */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #eeeeee;
    }
    
    /* 強制側邊欄內所有文字顏色為深灰，防止白底白字 */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] p {
        color: #333333 !important;
    }

    /* 標題區塊 */
    .title-container {
        display: flex; justify-content: space-between; align-items: baseline;
        border-bottom: 3px solid #1a237e; padding-bottom: 10px; margin-bottom: 20px;
    }
    .main-title {
        color: #1a237e; font-weight: 800; font-size: 32px; letter-spacing: 1px;
    }
    .author-tag {
        font-size: 14px; color: #fff; background-color: #1a237e; 
        padding: 4px 12px; border-radius: 4px; margin-left: 10px; 
        vertical-align: middle; font-weight: 500;
    }
    .sub-title {
        color: #555; font-size: 16px; font-weight: 600; text-transform: uppercase;
    }
    
    /* 專業卡片樣式 */
    .horse-card {
        background-color: white; padding: 20px; border-radius: 4px; 
        border: 1px solid #e0e0e0; border-top: 4px solid #1a237e;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 15px;
    }
    .top-pick-card {
        background-color: #fff; border-top: 4px solid #c62828; 
        border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0; border-bottom: 1px solid #e0e0e0;
    }
    
    /* 數據標籤 */
    .metric-label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
    .metric-value { font-size: 24px; font-weight: 700; color: #222; font-family: 'Roboto Mono', monospace; }
    
    /* 狀態標籤 */
    .status-tag {
        display: inline-block; padding: 2px 8px; border-radius: 2px; 
        font-size: 11px; font-weight: bold; text-transform: uppercase;
    }
    .tag-drop { background-color: #ffebee; color: #c62828; } 
    .tag-rise { background-color: #e8f5e9; color: #2e7d32; } 
    .tag-top { background-color: #1a237e; color: white; }    
    
    /* 按鈕與連結 */
    .stButton>button {
        background-color: #1a237e; color: white; border-radius: 4px; 
        height: 45px; font-weight: 600; border: none; text-transform: uppercase;
    }
    .stButton>button:hover { background-color: #283593; }
</style>
""", unsafe_allow_html=True)

# 標題
st.markdown("""
<div class="title-container">
    <div>
        <span class="main-title">賽馬智腦</span>
        <span class="author-tag">By Jay</span>
    </div>
    <div class="sub-title">REAL-TIME ODDS TRACKER</div>
</div>
""", unsafe_allow_html=True)

# ===================== 2. 內建資料庫 =====================
JOCKEY_RANK = {
    'Z Purton': 9.2, '潘頓': 9.2, 'J McDonald': 8.5, '麥道朗': 8.5, 'J Moreira': 6.5, '莫雷拉': 6.5, 
    'C Williams': 5.9, '韋紀力': 5.9, 'R Moore': 5.9, '莫雅': 5.9, 'H Bowman': 4.8, '布文': 4.8, 
    'C Y Ho': 4.2, '何澤堯': 4.2, 'L Ferraris': 3.8, '霍宏聲': 3.8, 'R Kingscote': 3.8, '金美琪': 3.8, 
    'A Atzeni': 3.7, '艾兆禮': 3.7, 'B Avdulla': 3.7, '艾道拿': 3.7, 'P N Wong': 3.4, '黃寶妮': 3.4, 
    'T Marquand': 3.3, '馬昆': 3.3, 'H Doyle': 3.3, '杜苑欣': 3.3, 'E C W Wong': 3.2, '黃智弘': 3.2, 
    'K C Leung': 3.2, '梁家俊': 3.2, 'B Shinn': 3.0, '薛恩': 3.0, 'K Teetan': 2.8, '田泰安': 2.8, 
    'H Bentley': 2.7, '班德禮': 2.7, 'M F Poon': 2.6, '潘明輝': 2.6, 'C L Chau': 2.4, '周俊樂': 2.4, 
    'M Chadwick': 2.4, '蔡明紹': 2.4, 'A Badel': 2.4, '巴度': 2.4, 'L Hewitson': 2.3, '希威森': 2.3, 
    'J Orman': 2.2, '奧文': 2.2, 'K De Melo': 1.9, '董明朗': 1.9, 'M L Yeung': 1.8, '楊明綸': 1.8, 
    'Y L Chung': 1.8, '鍾易禮': 1.8, 'A Hamelin': 1.7, '賀銘年': 1.7, 'H T Mo': 1.3, '巫顯東': 1.3, 
    'B Thompson': 0.9, '湯普新': 0.9, 'A Pouchin': 0.8, '普珍宜': 0.8
}
TRAINER_RANK = {
    'J Size': 4.4, '蔡約翰': 4.4, 'K L Man': 4.3, '文家良': 4.3, 'K W Lui': 4.0, '呂健威': 4.0, 
    'D Eustace': 3.9, '游達榮': 3.9, 'C Fownes': 3.9, '方嘉柏': 3.9, 'P F Yiu': 3.7, '姚本輝': 3.7, 
    'D A Hayes': 3.7, '大衛希斯': 3.7, 'M Newnham': 3.6, '廖康銘': 3.6, 'W Y So': 3.4, '蘇偉賢': 3.4, 
    'W K Mo': 3.3, '巫偉傑': 3.3, 'F C Lor': 3.2, '羅富全': 3.2, 'C H Yip': 3.2, '葉楚航': 3.2, 
    'C S Shum': 3.1, '沈集成': 3.1, 'K H Ting': 3.1, '丁冠豪': 3.1, 'A S Cruz': 3.0, '告東尼': 3.0, 
    'P C Ng': 2.5, '伍鵬志': 2.5, 'D J Whyte': 2.5, '韋達': 2.5, 'Y S Tsui': 2.5, '徐雨石': 2.5, 
    'J Richards': 2.3, '黎昭昇': 2.3, 'D J Hall': 2.3, '賀賢': 2.3, 'C W Chang': 2.2, '鄭俊偉': 2.2, 
    'T P Yung': 2.1, '容天鵬': 2.1
}
def get_ability_score(name, rank_dict):
    for key in rank_dict:
        if key in name or name in key: return rank_dict[key]
    return 2.0

# ===================== 3. 解析函數 =====================
def parse_odds_data(text):
    rows = []
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    i = 0
    while i < len(lines):
        if re.match(r'^\d+$', lines[i]):
            try:
                no = int(lines[i])
                name = lines[i+1] if i+1 < len(lines) else "未知"
                win = 0.0
                if i+2 < len(lines):
                    nums = re.findall(r'\d+\.?\d*', lines[i+2])
                    if nums: win = float(nums[0])
                if win > 0:
                    rows.append({"馬號": no, "馬名": name, "現價": win})
                    i += 3
                    continue
            except: pass
        i += 1
    if rows: return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

def parse_info_data(text):
    rows = []
    lines = text.strip().split('\n')
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 8 and parts[0].isdigit():
            try:
                no = int(parts[0])
                chn_pattern = re.compile(r'[\u4e00-\u9fa5]+')
                chn_words = [p for p in parts if chn_pattern.match(p)]
                if len(chn_words) >= 3:
                    rows.append({"馬號": no, "騎師": chn_words[1], "練馬師": chn_words[2]})
            except: continue
    if rows: return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

# ===================== 4. 側邊欄導航 (修復文字顯示) =====================
with st.sidebar:
    st.markdown("### 賽事導航")
    selected_race = st.selectbox("選擇場次", options=range(1, 15), format_func=lambda x: f"第 {x} 場 (Race {x})")
    st.divider()
    
    st.markdown("### 管理員登入")
    password = st.text_input("輸入密碼", type="password")
    is_admin = (password == "jay123")

    if is_admin:
        st.success("已解鎖編輯權限")
    
    st_autorefresh(interval=10000, key="data_refresher")

current_race_data = race_storage[selected_race]

# ===================== 5. 管理員控制台 =====================
if is_admin:
    with st.expander(f"數據控制台 - 第 {selected_race} 場", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 賠率表來源")
            new_odds = st.text_area("Odds Input", value=current_race_data["raw_odds_text"], height=150, key=f"odds_{selected_race}")
        with c2:
            st.markdown("#### 排位表來源")
            new_info = st.text_area("Info Input", value=current_race_data["raw_info_text"], height=150, key=f"info_{selected_race}")
        
        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            if st.button(f"發布第 {selected_race} 場更新", use_container_width=True, type="primary"):
                df_odds = parse_odds_data(new_odds)
                if not df_odds.empty:
                    df_info = parse_info_data(new_info) if new_info else pd.DataFrame()
                    if not df_info.empty: df_odds = df_odds.join(df_info, how="left")
                    
                    for col in ["騎師", "練馬師"]:
                        if col not in df_odds.columns: df_odds[col] = "未知"
                        df_odds[col] = df_odds[col].fillna("未知")
                    
                    if not current_race_data["current_df"].empty:
                        current_race_data["last_df"] = current_race_data["current_df"]
                    else:
                        current_race_data["last_df"] = df_odds
                        
                    current_race_data["current_df"] = df_odds
                    current_race_data["raw_odds_text"] = new_odds
                    current_race_data["raw_info_text"] = new_info
                    current_race_data["last_update"] = datetime.now().strftime("%H:%M:%S")
                    
                    st.success("數據已更新")
                    st.rerun()
                else:
                    st.error("解析失敗")
        
        with col_btn2:
            if st.button(f"清空第 {selected_race} 場", use_container_width=True):
                race_storage[selected_race] = {
                    "current_df": pd.DataFrame(), "last_df": pd.DataFrame(),
                    "last_update": "無數據", "raw_odds_text": "", "raw_info_text": ""
                }
                st.rerun()

# ===================== 6. 分析報告展示 =====================
st.markdown(f"#### 第 {selected_race} 場賽事分析報告")

if not current_race_data["current_df"].empty:
    df = current_race_data["current_df"].copy()
    last_df = current_race_data["last_df"].copy()
    update_time = current_race_data["last_update"]
    
    last_odds = last_df[["現價"]].rename(columns={"現價": "上回賠率"})
    if "上回賠率" not in df.columns:
        df = df.join(last_odds, how="left")
        df["上回賠率"] = df["上回賠率"].fillna(df["現價"])
    
    df["真實走勢(%)"] = ((df["上回賠率"] - df["現價"]) / df["上回賠率"] * 100).fillna(0).round(1)
    
    def calculate_score(row):
        s = 0
        trend = row["真實走勢(%)"]
        if trend >= 15: s += 50
        elif trend >= 10: s += 35
        elif trend >= 5: s += 20
        elif trend <= -10: s -= 20
        
        if row["現價"] <= 5.0: s += 25
        elif row["現價"] <= 10.0: s += 10
        
        j = get_ability_score(row["騎師"], JOCKEY_RANK)
        t = get_ability_score(row["練馬師"], TRAINER_RANK)
        s += j * 2.5
        s += t * 1.5
        return round(s, 1)

    df["得分"] = df.apply(calculate_score, axis=1)
    df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index()
    
    st.caption(f"DATA UPDATED: {update_time}")
    
    # 重心馬卡片
    top_picks = df[df["得分"] >= 65]
    if not top_picks.empty:
        st.markdown("**重心推薦 TOP PICKS**")
        cols = st.columns(min(len(top_picks), 3))
        for idx, col in enumerate(cols):
            if idx < len(top_picks):
                row = top_picks.iloc[idx]
                with col:
                    t_val = row["真實走勢(%)"]
                    if t_val > 0: 
                        trend_html = f"<span class='status-tag tag-drop'>落飛 {abs(t_val)}%</span>"
                    elif t_val < 0: 
                        trend_html = f"<span class='status-tag tag-rise'>回飛 {abs(t_val)}%</span>"
                    else: 
                        trend_html = "<span style='color:#999'>-</span>"
                    
                    st.markdown(f"""
                    <div class="horse-card top-pick-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:18px; font-weight:800; color:#1a237e;">#{row['馬號']} {row['馬名']}</div>
                            <span class="status-tag tag-top">TOP</span>
                        </div>
                        <div style="margin:15px 0; display:flex; justify-content:space-between;">
                            <div><div class="metric-label">ODDS</div><div class="metric-value">{row['現價']}</div></div>
                            <div style="text-align:right;"><div class="metric-label">SCORE</div><div class="metric-value" style="color:#c62828;">{row['得分']}</div></div>
                        </div>
                        <div style="border-top:1px solid #eee; padding-top:8px; font-size:12px; display:flex; justify-content:space-between;">
                            {trend_html}
                            <span style="color:#666; font-weight:600;">{row['騎師']} / {row['練馬師']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # 完整表格
    st.markdown("**全場形勢 GENERAL OVERVIEW**")
    st.dataframe(
        df[["馬號", "馬名", "現價", "上回賠率", "真實走勢(%)", "騎師", "練馬師", "得分"]],
        use_container_width=True, hide_index=True,
        column_config={
            "馬號": st.column_config.NumberColumn(format="%d", width="small"),
            "現價": st.column_config.NumberColumn(format="%.1f"),
            "真實走勢(%)": st.column_config.NumberColumn("走勢%", format="%.1f"),
            "得分": st.column_config.ProgressColumn("評分", format="%.1f", min_value=0, max_value=100)
        }
    )

else:
    st.info(f"等待數據更新 (Status: Waiting for data input - Race {selected_race})")
    if is_admin:
        st.write("請在上方控制台輸入並發布數據。")
