import streamlit as st
import pandas as pd
import re
from datetime import datetime

# ===================== 0. 頁面配置與 CSS 美化 =====================
# 移除 page_icon 參數，讓它不顯示預設的 emoji
st.set_page_config(page_title="HKJC 賽馬智腦 By Jay", layout="wide")

# 自定義 CSS
st.markdown("""
<style>
    /* 全局字體與背景 */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* 主標題容器 */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 15px;
        margin-bottom: 30px;
    }
    
    /* 左側標題樣式 */
    .main-title {
        color: #1a237e; /* 深藍色 */
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 800;
        font-size: 2.5em;
        margin: 0;
    }
    
    /* 署名樣式 */
    .author-tag {
        font-size: 0.4em;
        color: #757575;
        font-weight: normal;
        margin-left: 10px;
        vertical-align: middle;
        background-color: #e8eaf6;
        padding: 4px 10px;
        border-radius: 15px;
    }
    
    /* 右側副標題樣式 */
    .sub-title {
        color: #5c6bc0;
        font-weight: 600;
        font-size: 1.2em;
        text-align: right;
    }
    
    /* 資訊卡片樣式 */
    .horse-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 15px;
        border-left: 6px solid #1a237e;
        transition: transform 0.2s;
    }
    .horse-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(0,0,0,0.1);
    }
    
    /* 高分馬卡片特別樣式 */
    .top-pick-card {
        background-color: #fffde7; /* 淺黃色背景 */
        border-left: 6px solid #fbc02d; /* 金色邊框 */
        border: 1px solid #fff9c4;
    }
    
    /* 數據指標字體 */
    .metric-label { font-size: 0.85em; color: #757575; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 1.4em; font-weight: 800; color: #333; margin-top: 2px; }
    
    /* 按鈕美化 */
    .stButton>button {
        background-color: #1a237e;
        color: white;
        border-radius: 8px;
        height: 55px;
        font-size: 18px;
        font-weight: 600;
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stButton>button:hover {
        background-color: #283593;
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    }
    
    /* 連結樣式 */
    a { text-decoration: none; color: #1565c0; font-weight: 500; }
    a:hover { text-decoration: underline; }
</style>
""", unsafe_allow_html=True)

# 標題區 (使用 HTML 實現左右佈局)
st.markdown("""
<div class="header-container">
    <div>
        <h1 class="main-title">
            賽馬智腦 <span class="author-tag">By Jay</span>
        </h1>
    </div>
    <div class="sub-title">
        智能賠率追蹤系統
    </div>
</div>
""", unsafe_allow_html=True)

# 初始化 session_state
if 'history_df' not in st.session_state:
    st.session_state.history_df = pd.DataFrame()
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = "尚未更新"

# ===================== 1. 內建資料庫 (維持不變) =====================
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

# ===================== 2. 輸入面板 =====================
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.info("📊 步驟 1: 貼上賠率")
        st.markdown("[🔗 點此打開 51saima 賠率頁](https://www.51saima.com/mobi/odds.jsp)")
        raw_odds = st.text_area("", height=150, key="odds_input", placeholder="全選複製網頁內容 -> 在此貼上...", label_visibility="collapsed")
    with col2:
        st.info("📋 步驟 2: 貼上排位 (選填)")
        st.markdown("[🔗 點此打開馬會排位頁](https://racing.hkjc.com/racing/information/Chinese/racing/RaceCard.aspx)")
        raw_info = st.text_area("", height=150, key="info_input", placeholder="全選複製排位表 -> 在此貼上...", label_visibility="collapsed")

    update_btn = st.button("🚀 開始智能分析 / 更新賠率", use_container_width=True)

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

# ===================== 4. 分析與結果展示 =====================
if update_btn and raw_odds:
    current_df = parse_odds_data(raw_odds)
    
    if not current_df.empty:
        # --- 數據處理 ---
        last_df = st.session_state.history_df
        if not last_df.empty:
            last_odds = last_df[["現價"]].rename(columns={"現價": "上回賠率"})
            merged_df = current_df.join(last_odds, how="left")
            merged_df["上回賠率"] = merged_df["上回賠率"].fillna(merged_df["現價"])
        else:
            merged_df = current_df
            merged_df["上回賠率"] = merged_df["現價"]
            
        merged_df["真實走勢(%)"] = ((merged_df["上回賠率"] - merged_df["現價"]) / merged_df["上回賠率"] * 100).fillna(0).round(1)
        st.session_state.history_df = current_df
        st.session_state.last_update_time = datetime.now().strftime("%H:%M:%S")
        
        if raw_info:
            df_info = parse_info_data(raw_info)
            if not df_info.empty:
                merged_df = merged_df.join(df_info, how="left")
        
        if "騎師" not in merged_df.columns:
            merged_df["騎師"] = "未知"
            merged_df["練馬師"] = "未知"
            
        merged_df["騎師"] = merged_df["騎師"].fillna("未知")
        merged_df["練馬師"] = merged_df["練馬師"].fillna("未知")

        # --- 綜合評分邏輯 ---
        def calculate_score(row):
            s = 0
            trend = row["真實走勢(%)"]
            if trend >= 15: s += 50
            elif trend >= 10: s += 35
            elif trend >= 5: s += 20
            elif trend <= -10: s -= 20
            
            if row["現價"] <= 5.0: s += 25
            elif row["現價"] <= 10.0: s += 10
            
            j_score = get_ability_score(row["騎師"], JOCKEY_RANK)
            t_score = get_ability_score(row["練馬師"], TRAINER_RANK)
            s += j_score * 2.5
            s += t_score * 1.5
            return round(s, 1)

        merged_df["得分"] = merged_df.apply(calculate_score, axis=1)
        merged_df = merged_df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index()

        # --- 美化展示區塊 ---
        st.markdown(f"### 📈 分析報告 <span style='font-size:0.6em;color:grey;font-weight:normal'>(數據更新於 {st.session_state.last_update_time})</span>", unsafe_allow_html=True)
        
        # 1. 重點推薦區 (Card View)
        top_picks = merged_df[merged_df["得分"] >= 65]
        if not top_picks.empty:
            st.success(f"🔥 AI 鎖定 {len(top_picks)} 匹高勝率重心馬！")
            
            num_cards = min(len(top_picks), 3)
            cols = st.columns(num_cards)
            
            for idx, col in enumerate(cols):
                if idx < len(top_picks):
                    row = top_picks.iloc[idx]
                    with col:
                        trend_val = row["真實走勢(%)"]
                        if trend_val > 0:
                            trend_color = "#d32f2f" # 紅
                            trend_arrow = "🔻落飛"
                        elif trend_val < 0:
                            trend_color = "#388e3c" # 綠
                            trend_arrow = "🔺回飛"
                        else:
                            trend_color = "#9e9e9e"
                            trend_arrow = "-"
                        
                        st.markdown(f"""
                        <div class="horse-card top-pick-card">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                                <div style="font-size:1.4em; font-weight:bold; color:#1a237e;">
                                    #{row['馬號']} {row['馬名']}
                                </div>
                                <div style="background:#fbc02d; color:#fff; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:0.8em;">
                                    TOP PICK
                                </div>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:15px;">
                                <div>
                                    <div class="metric-label">獨贏賠率</div>
                                    <div class="metric-value">{row['現價']}</div>
                                </div>
                                <div style="text-align:right;">
                                    <div class="metric-label">AI 綜合分</div>
                                    <div class="metric-value" style="color:#e65100;">{row['得分']}</div>
                                </div>
                            </div>
                            <div style="border-top:1px solid #e0e0e0; padding-top:10px; font-size:0.9em;">
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span style="color:{trend_color}; font-weight:bold; font-size:1.1em;">
                                        {trend_arrow} {abs(trend_val)}%
                                    </span>
                                    <span style="color:#555;">
                                        {row['騎師']} / {row['練馬師']}
                                    </span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("💡 本場形勢較為平均，暫無超高分心水。建議參考下方列表的落飛馬匹。")

        # 2. 完整列表
        st.markdown("#### 📋 全場形勢總覽")
        
        display_df = merged_df[["馬號", "馬名", "現價", "上回賠率", "真實走勢(%)", "騎師", "練馬師", "得分"]].copy()
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "馬號": st.column_config.NumberColumn(format="%d", width="small"),
                "現價": st.column_config.NumberColumn(format="%.1f"),
                "上回賠率": st.column_config.NumberColumn(format="%.1f"),
                "真實走勢(%)": st.column_config.NumberColumn(
                    "實時走勢",
                    format="%.1f%%",
                    help="正數(紅色)代表落飛，負數(綠色)代表回飛"
                ),
                "得分": st.column_config.ProgressColumn(
                    "AI 評分",
                    format="%.1f",
                    min_value=0,
                    max_value=100,
                ),
            }
        )

    else:
        st.error("⚠️ 解析失敗，請確認貼上的內容是否包含正確的賠率格式。")

elif not raw_odds:
    # 歡迎畫面
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; color: #757575;">
        <h2 style="color:#1a237e; margin-bottom:10px;">👋 歡迎使用</h2>
        <p style="font-size:1.1em;">請在上方 <b>步驟 1</b> 貼上賠率表，即可開始實時分析。</p>
        <div style="margin-top:30px; display:flex; justify-content:center; gap:20px;">
            <div style="background:white; padding:15px; border-radius:8px; width:150px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:2em;">📉</div>
                <div style="font-weight:bold; margin-top:5px;">落飛追蹤</div>
            </div>
            <div style="background:white; padding:15px; border-radius:8px; width:150px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:2em;">🏇</div>
                <div style="font-weight:bold; margin-top:5px;">騎練評級</div>
            </div>
            <div style="background:white; padding:15px; border-radius:8px; width:150px; box-shadow:0 2px 5px rgba(0,0,0,0.05);">
                <div style="font-size:2em;">🤖</div>
                <div style="font-weight:bold; margin-top:5px;">AI 評分</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)









