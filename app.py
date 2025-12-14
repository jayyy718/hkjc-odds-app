import streamlit as st
import pandas as pd
import re
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ===================== 0. 全局數據共享核心 =====================
# 這是實現「一人輸入，萬人觀看」的關鍵
# 我們使用 @st.cache_resource 來創建一個跨用戶的全局容器

@st.cache_resource
def get_global_data():
    return {
        "current_df": pd.DataFrame(),    # 當前數據
        "last_df": pd.DataFrame(),       # 上一次數據 (用於計算變動)
        "last_update": "尚未更新",        # 更新時間
        "raw_odds_text": "",             # 緩存輸入框文字
        "raw_info_text": ""
    }

global_data = get_global_data()

# ===================== 1. 頁面配置與 CSS =====================
st.set_page_config(page_title="HKJC 賽馬智腦 By Jay", layout="wide", page_icon="🏇")

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    
    /* 標題樣式 */
    .title-container {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        border-bottom: 2px solid #e0e0e0;
        padding-bottom: 15px;
        margin-bottom: 20px;
    }
    .main-title {
        color: #1a237e;
        font-family: sans-serif;
        font-weight: 800;
        font-size: 40px;
        margin: 0;
    }
    .author-tag {
        font-size: 16px;
        color: #666;
        font-weight: normal;
        margin-left: 10px;
        background-color: #e8eaf6;
        padding: 4px 10px;
        border-radius: 12px;
        vertical-align: middle;
    }
    .sub-title {
        color: #5c6bc0;
        font-size: 20px;
        font-weight: 600;
    }
    
    /* 卡片樣式 */
    .horse-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 15px;
        border-left: 6px solid #1a237e;
    }
    .top-pick-card {
        background-color: #fffde7;
        border-left: 6px solid #fbc02d;
    }
    
    /* 指標字體 */
    .metric-label { font-size: 0.85em; color: #757575; }
    .metric-value { font-size: 1.4em; font-weight: 800; color: #333; }
    
    /* 按鈕 */
    .stButton>button {
        background-color: #1a237e;
        color: white;
        border-radius: 8px;
        height: 55px;
        font-size: 18px;
        font-weight: 600;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# 頁面標題
st.markdown("""
<div class="title-container">
    <div style="display:flex; align-items:center;">
        <span class="main-title">賽馬智腦</span>
        <span class="author-tag">By Jay</span>
    </div>
    <div class="sub-title">智能賠率追蹤系統 (實時廣播)</div>
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

# ===================== 4. 管理員控制台 (Sidebar Login) =====================
with st.sidebar:
    st.header("🔐 管理員登入")
    password = st.text_input("輸入密碼以解鎖編輯", type="password")
    is_admin = (password == "jay123") # 設定您的密碼

    if is_admin:
        st.success("✅ 已解鎖：您可以廣播數據")
    else:
        st.info("👀 訪客模式：等待數據更新")

    # 每 10 秒自動刷新一次，確保觀眾看到最新數據
    st_autorefresh(interval=10000, key="data_refresher")

# ===================== 5. 數據輸入與發布 (僅管理員可見) =====================
if is_admin:
    with st.expander("📝 數據控制台 (點擊展開)", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 1. 賠率輸入")
            st.markdown("[🔗 51saima](https://www.51saima.com/mobi/odds.jsp)")
            new_odds = st.text_area("賠率表", value=global_data["raw_odds_text"], height=150, key="admin_odds")
        with c2:
            st.markdown("### 2. 排位輸入")
            st.markdown("[🔗 馬會排位](https://racing.hkjc.com/racing/information/Chinese/racing/RaceCard.aspx)")
            new_info = st.text_area("排位表", value=global_data["raw_info_text"], height=150, key="admin_info")
        
        if st.button("🚀 發布更新 (Broadcast)", use_container_width=True):
            # 解析
            current_df = parse_odds_data(new_odds)
            
            if not current_df.empty:
                # 處理排位
                info_df = parse_info_data(new_info) if new_info else pd.DataFrame()
                
                if not info_df.empty:
                    current_df = current_df.join(info_df, how="left")
                
                if "騎師" not in current_df.columns:
                    current_df["騎師"] = "未知"
                    current_df["練馬師"] = "未知"
                
                current_df["騎師"] = current_df["騎師"].fillna("未知")
                current_df["練馬師"] = current_df["練馬師"].fillna("未知")
                
                # 更新全局數據
                # 將舊的 current 移到 last
                if not global_data["current_df"].empty:
                    global_data["last_df"] = global_data["current_df"]
                else:
                    global_data["last_df"] = current_df # 初始化
                
                global_data["current_df"] = current_df
                global_data["raw_odds_text"] = new_odds
                global_data["raw_info_text"] = new_info
                global_data["last_update"] = datetime.now().strftime("%H:%M:%S")
                
                st.success("✅ 數據已發布！所有訪客都能看到最新結果。")
                st.rerun()
            else:
                st.error("解析失敗，請檢查賠率格式。")

# ===================== 6. 觀眾展示區 (所有人可見) =====================

if not global_data["current_df"].empty:
    # 獲取全局數據
    df = global_data["current_df"].copy()
    last_df = global_data["last_df"].copy()
    
    # 計算變動
    # 為了方便計算，我們先把 last_df 的 '現價' 改名
    last_odds = last_df[["現價"]].rename(columns={"現價": "上回賠率"})
    
    # 合併以計算變動 (必須以當前馬號為主)
    if "上回賠率" not in df.columns:
        df = df.join(last_odds, how="left")
        df["上回賠率"] = df["上回賠率"].fillna(df["現價"])
    
    df["真實走勢(%)"] = ((df["上回賠率"] - df["現價"]) / df["上回賠率"] * 100).fillna(0).round(1)
    
    # 評分邏輯
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

    df["得分"] = df.apply(calculate_score, axis=1)
    df = df.sort_values(["得分", "現價"], ascending=[False, True]).reset_index()
    
    # --- UI 展示 ---
    st.markdown(f"### 📈 實時分析報告 <span style='font-size:0.6em;color:grey;font-weight:normal'>(更新於 {global_data['last_update']})</span>", unsafe_allow_html=True)
    
    # 卡片視圖
    top_picks = df[df["得分"] >= 65]
    if not top_picks.empty:
        st.success(f"🔥 AI 鎖定 {len(top_picks)} 匹重心馬！")
        cols = st.columns(min(len(top_picks), 3))
        for idx, col in enumerate(cols):
            if idx < len(top_picks):
                row = top_picks.iloc[idx]
                with col:
                    trend_val = row["真實走勢(%)"]
                    if trend_val > 0: c="#d32f2f"; a="🔻落飛"
                    elif trend_val < 0: c="#388e3c"; a="🔺回飛"
                    else: c="#9e9e9e"; a="-"
                    
                    st.markdown(f"""
                    <div class="horse-card top-pick-card">
                        <div style="font-size:1.4em; font-weight:bold; color:#1a237e;">#{row['馬號']} {row['馬名']}</div>
                        <div style="display:flex; justify-content:space-between; margin:10px 0;">
                            <div><div class="metric-label">獨贏</div><div class="metric-value">{row['現價']}</div></div>
                            <div style="text-align:right;"><div class="metric-label">得分</div><div class="metric-value" style="color:#e65100;">{row['得分']}</div></div>
                        </div>
                        <div style="border-top:1px solid #e0e0e0; padding-top:10px;">
                            <span style="color:{c}; font-weight:bold;">{a} {abs(trend_val)}%</span>
                            <span style="float:right; color:#555;">{row['騎師']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # 列表視圖
    st.markdown("#### 📋 全場形勢")
    st.dataframe(
        df[["馬號", "馬名", "現價", "上回賠率", "真實走勢(%)", "騎師", "練馬師", "得分"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "馬號": st.column_config.NumberColumn(format="%d", width="small"),
            "現價": st.column_config.NumberColumn(format="%.1f"),
            "上回賠率": st.column_config.NumberColumn(format="%.1f"),
            "真實走勢(%)": st.column_config.NumberColumn("實時走勢", format="%.1f%%"),
            "得分": st.column_config.ProgressColumn("AI 評分", format="%.1f", min_value=0, max_value=100),
        }
    )

else:
    # 等待畫面
    if not is_admin:
        st.markdown("""
        <div style="text-align:center; padding: 80px 20px; color: #757575;">
            <div style="font-size:3em; margin-bottom:20px;">📡</div>
            <h2 style="color:#1a237e;">等待賽事數據廣播...</h2>
            <p style="font-size:1.1em;">管理員尚未發布最新賠率。</p>
            <p>頁面每 10 秒會自動檢查一次，請保持開啟。</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("👋 管理員模式：請在上方控制台輸入數據並發布。")
