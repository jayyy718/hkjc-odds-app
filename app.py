import streamlit as st
import pandas as pd
import re
from datetime import datetime

# ===================== 頁面初始化 =====================
st.set_page_config(page_title="HKJC 實時智能賽馬分析", layout="wide")
st.title("🏇 HKJC 實時智能賽馬分析系統 (2024/25 數據版)")
st.caption("功能：實時賠率變動追蹤 + 騎練實力分析 + 2024/25 勝率大數據模型")

# 初始化 session_state 用來存儲歷史賠率
if 'history_df' not in st.session_state:
    st.session_state.history_df = pd.DataFrame()
if 'last_update_time' not in st.session_state:
    st.session_state.last_update_time = "尚未更新"

# ===================== 1. 基於真實數據的評分庫 =====================
# 分數 = (真實勝率 / 25%) * 10，滿分 10 分
# 數據來源：2024-2025 賽季統計
JOCKEY_RANK = {
    'Z Purton': 9.2, '潘頓': 9.2,
    'J McDonald': 8.5, '麥道朗': 8.5,
    'J Moreira': 6.5, '莫雷拉': 6.5,
    'C Williams': 5.9, '韋紀力': 5.9,
    'R Moore': 5.9, '莫雅': 5.9,
    'H Bowman': 4.8, '布文': 4.8,
    'C Y Ho': 4.2, '何澤堯': 4.2,
    'L Ferraris': 3.8, '霍宏聲': 3.8,
    'R Kingscote': 3.8, '金美琪': 3.8,
    'A Atzeni': 3.7, '艾兆禮': 3.7,
    'B Avdulla': 3.7, '艾道拿': 3.7,
    'P N Wong': 3.4, '黃寶妮': 3.4,
    'T Marquand': 3.3, '馬昆': 3.3,
    'H Doyle': 3.3, '杜苑欣': 3.3,
    'E C W Wong': 3.2, '黃智弘': 3.2,
    'K C Leung': 3.2, '梁家俊': 3.2,
    'B Shinn': 3.0, '薛恩': 3.0,
    'K Teetan': 2.8, '田泰安': 2.8,
    'H Bentley': 2.7, '班德禮': 2.7,
    'M F Poon': 2.6, '潘明輝': 2.6,
    'C L Chau': 2.4, '周俊樂': 2.4,
    'M Chadwick': 2.4, '蔡明紹': 2.4,
    'A Badel': 2.4, '巴度': 2.4,
    'L Hewitson': 2.3, '希威森': 2.3,
    'J Orman': 2.2, '奧文': 2.2,
    'K De Melo': 1.9, '董明朗': 1.9,
    'M L Yeung': 1.8, '楊明綸': 1.8,
    'Y L Chung': 1.8, '鍾易禮': 1.8,
    'A Hamelin': 1.7, '賀銘年': 1.7,
    'H T Mo': 1.3, '巫顯東': 1.3,
    'B Thompson': 0.9, '湯普新': 0.9,
    'A Pouchin': 0.8, '普珍宜': 0.8
}

# 練馬師勝率較平均，分數差異較小
TRAINER_RANK = {
    'J Size': 4.4, '蔡約翰': 4.4,
    'K L Man': 4.3, '文家良': 4.3,
    'K W Lui': 4.0, '呂健威': 4.0,
    'D Eustace': 3.9, '游達榮': 3.9,
    'C Fownes': 3.9, '方嘉柏': 3.9,
    'P F Yiu': 3.7, '姚本輝': 3.7,
    'D A Hayes': 3.7, '大衛希斯': 3.7,
    'M Newnham': 3.6, '廖康銘': 3.6,
    'W Y So': 3.4, '蘇偉賢': 3.4,
    'W K Mo': 3.3, '巫偉傑': 3.3,
    'F C Lor': 3.2, '羅富全': 3.2,
    'C H Yip': 3.2, '葉楚航': 3.2,
    'C S Shum': 3.1, '沈集成': 3.1,
    'K H Ting': 3.1, '丁冠豪': 3.1,
    'A S Cruz': 3.0, '告東尼': 3.0,
    'P C Ng': 2.5, '伍鵬志': 2.5,
    'D J Whyte': 2.5, '韋達': 2.5,
    'Y S Tsui': 2.5, '徐雨石': 2.5,
    'J Richards': 2.3, '黎昭昇': 2.3,
    'D J Hall': 2.3, '賀賢': 2.3,
    'C W Chang': 2.2, '鄭俊偉': 2.2,
    'T P Yung': 2.1, '容天鵬': 2.1
}

def get_ability_score(name, rank_dict):
    # 模糊匹配：只要名字包含關鍵字就給分
    for key in rank_dict:
        if key in name or name in key: 
            return rank_dict[key]
    return 2.0 # 預設分數調低，凸顯強者

# ===================== 2. 輸入介面 =====================
c1, c2 = st.columns(2)

with c1:
    st.markdown("### 1️⃣ 賠率輸入 (支援多次更新)")
    st.link_button("👉 打開 51saima (賠率表)", "https://www.51saima.com/mobi/odds.jsp", use_container_width=True)
    raw_odds = st.text_area("在此貼上最新賠率：", height=200, key="odds_input", placeholder="全選複製賠率頁面文字 -> 貼上")
    
    # 新增一個「更新數據」按鈕
    update_btn = st.button("🔄 更新賠率並計算變動", type="primary", use_container_width=True)

with c2:
    st.markdown("### 2️⃣ 排位表 (只貼一次即可)")
    st.link_button("👉 打開馬會 (排位表)", "https://racing.hkjc.com/racing/information/Chinese/racing/RaceCard.aspx", use_container_width=True)
    raw_info = st.text_area("在此貼上排位表：", height=200, key="info_input", placeholder="全選複製排位頁面文字 -> 貼上")

# ===================== 3. 核心解析函數 =====================

def parse_odds_data(text):
    """解析賠率數據 (支援 51saima 及馬會格式)"""
    rows = []
    # 移除空行
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    i = 0
    while i < len(lines):
        # 尋找馬號開頭的行
        if re.match(r'^\d+$', lines[i]):
            try:
                no = int(lines[i])
                name = lines[i+1] if i+1 < len(lines) else "未知"
                win = 0.0
                
                # 賠率通常在馬名後的下一行或下兩行
                # 這裡假設結構：馬號 -> 馬名 -> 賠率
                if i+2 < len(lines):
                    # 抓取該行所有小數點數字
                    nums = re.findall(r'\d+\.?\d*', lines[i+2])
                    if nums: 
                        win = float(nums[0]) # 取第一個數字作為獨贏
                
                if win > 0:
                    rows.append({"馬號": no, "馬名": name, "現價": win})
                    i += 3 # 跳過已處理的行
                    continue
            except: pass
        i += 1
    
    if rows:
        return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

def parse_info_data(text):
    """解析排位表 (抓取騎師與練馬師)"""
    rows = []
    lines = text.strip().split('\n')
    for line in lines:
        parts = line.strip().split()
        # 有效行通常包含馬號且有多個欄位
        if len(parts) >= 8 and parts[0].isdigit():
            try:
                no = int(parts[0])
                # 利用中文詞特徵提取
                # 預期順序：馬名 -> 騎師 -> 練馬師
                chn_pattern = re.compile(r'[\u4e00-\u9fa5]+')
                chn_words = [p for p in parts if chn_pattern.match(p)]
                
                if len(chn_words) >= 3:
                    rows.append({
                        "馬號": no,
                        "騎師": chn_words[1],
                        "練馬師": chn_words[2]
                    })
            except: continue
            
    if rows:
        return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")
    return pd.DataFrame()

# ===================== 4. 主邏輯與評分模型 =====================

if update_btn and raw_odds:
    # 1. 解析當前賠率
    current_df = parse_odds_data(raw_odds)
    
    if not current_df.empty:
        # 2. 處理歷史數據 (實時變動計算)
        last_df = st.session_state.history_df
        
        if not last_df.empty:
            # 有歷史數據 -> 進行合併與比對
            last_odds = last_df[["現價"]].rename(columns={"現價": "上回賠率"})
            merged_df = current_df.join(last_odds, how="left")
            # 填補缺失值 (若無上回賠率，則設為當前賠率)
            merged_df["上回賠率"] = merged_df["上回賠率"].fillna(merged_df["現價"])
        else:
            # 無歷史數據 -> 初始化
            merged_df = current_df
            merged_df["上回賠率"] = merged_df["現價"]
        
        # 計算真實變動 % (正數=落飛/跌價, 負數=回飛/升價)
        merged_df["真實走勢(%)"] = ((merged_df["上回賠率"] - merged_df["現價"]) / merged_df["上回賠率"] * 100).fillna(0).round(1)
        
        # 更新 Session State
        st.session_state.history_df = current_df
        st.session_state.last_update_time = datetime.now().strftime("%H:%M:%S")
        
        # 3. 結合排位表資訊
        if raw_info:
            df_info = parse_info_data(raw_info)
            if not df_info.empty:
                merged_df = merged_df.join(df_info, how="left")
                merged_df["騎師"] = merged_df["騎師"].fillna("未知")
                merged_df["練馬師"] = merged_df["練馬師"].fillna("未知")
            else:
                merged_df["騎師"] = "未知"
                merged_df["練馬師"] = "未知"
        else:
            merged_df["騎師"] = "未知"
            merged_df["練馬師"] = "未知"

        # 4. 綜合評分 (核心演算法)
        def calculate_score(row):
            s = 0
            
            # A. 走勢面 (基於真實變動)
            trend = row["真實走勢(%)"]
            if trend >= 15: s += 50      # 巨幅落飛
            elif trend >= 10: s += 35    # 大幅落飛
            elif trend >= 5: s += 20     # 明顯落飛
            elif trend <= -10: s -= 20   # 大幅回飛 (扣分)
            
            # B. 賠率面 (基於勝率統計)
            # 5倍以下勝率極高(27%)
            if row["現價"] <= 5.0: s += 25
            elif row["現價"] <= 10.0: s += 10
            
            # C. 實力面 (基於騎練排名)
            j_score = get_ability_score(row["騎師"], JOCKEY_RANK)
            t_score = get_ability_score(row["練馬師"], TRAINER_RANK)
            
            # 騎師權重較高 (2.5倍)
            s += j_score * 2.5
            # 練馬師權重 (1.5倍)
            s += t_score * 1.5
            
            return round(s, 1)

        merged_df["得分"] = merged_df.apply(calculate_score, axis=1)
        
        # 5. 視覺化格式設定
        def format_trend(val):
            if val > 0: return f"🔻跌 {abs(val)}%" # 紅色跌價(好事)
            if val < 0: return f"🔺升 {abs(val)}%" # 綠色升價(壞事)
            return "-"
            
        merged_df["走勢提示"] = merged_df["真實走勢(%)"].apply(format_trend)
        
        # 排序：得分優先 -> 賠率次之
        merged_df = merged_df.sort_values(["得分", "現價"], ascending=[False, True])
        
        # 重置索引以便顯示
        df_display = merged_df.reset_index()

        # ===================== 5. 結果顯示 =====================
        st.divider()
        st.subheader(f"📊 實時分析報告 (最後更新: {st.session_state.last_update_time})")
        
        # 高亮顯示高分馬 (得分 >= 65)
        top_picks = df_display[df_display["得分"] >= 65]
        
        if not top_picks.empty:
            st.success(f"🔥 發現 {len(top_picks)} 匹高勝率推薦馬！")
            st.dataframe(
                top_picks[["馬號", "馬名", "現價", "上回賠率", "走勢提示", "騎師", "練馬師", "得分"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("目前形勢較為平均，暫無超高分心水，建議觀察「走勢提示」尋找落飛馬。")
        
        # 實時落飛警報 (獨立於得分)
        drops = df_display[df_display["真實走勢(%)"] >= 5]
        if not drops.empty:
            st.warning(f"🚨 資金流警報：{', '.join(drops['馬名'].tolist())} 出現顯著落飛！")

        # 完整列表 (放在折疊區塊保持整潔)
        with st.expander("點擊查看全場詳細數據", expanded=True):
            st.dataframe(
                df_display[["馬號", "馬名", "現價", "上回賠率", "走勢提示", "騎師", "練馬師", "得分"]],
                use_container_width=True,
                hide_index=True
            )

    else:
        st.error("賠率表解析失敗，請確認複製內容包含馬號、馬名及賠率數據。")

elif not raw_odds:
    st.info("👋 請在左側貼上賠率表並按下「更新」按鈕開始分析。")








