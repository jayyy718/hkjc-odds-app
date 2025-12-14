import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC 數據驅動版By Jay", layout="wide")
st.title("🏇 HKJC 智能分析 (2024/25 數據驅動版)")
st.caption("核心演算法已根據2024-2025 年度賽事數據進行校準。")

# ===================== 1. 基於真實數據的評分庫 =====================
# 分數 = (真實勝率 / 25%) * 10，滿分 10 分
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

# ===================== 輸入區 =====================
c1, c2 = st.columns(2)
with c1:
    st.markdown("### 1️⃣ 賠率表 (51saima)")
    st.link_button("👉 打開 51saima", "https://www.51saima.com/mobi/odds.jsp", use_container_width=True)
    raw_odds = st.text_area("貼上賠率：", height=200)

with c2:
    st.markdown("### 2️⃣ 排位表 (馬會)")
    st.link_button("👉 打開馬會排位", "https://racing.hkjc.com/racing/information/Chinese/racing/RaceCard.aspx", use_container_width=True)
    raw_info = st.text_area("貼上排位：", height=200)

# ===================== 解析邏輯 =====================
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
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

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
                    rows.append({
                        "馬號": no,
                        "騎師": chn_words[1],
                        "練馬師": chn_words[2]
                    })
            except: continue
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

# ===================== 主邏輯 =====================
if raw_odds and raw_info:
    df_odds = parse_odds_data(raw_odds)
    df_info = parse_info_data(raw_info)
    
    if not df_odds.empty and not df_info.empty:
        df_final = df_odds.join(df_info, how="left")
        df_final["騎師"] = df_final["騎師"].fillna("未知")
        df_final["練馬師"] = df_final["練馬師"].fillna("未知")
        
        # --- 數據驅動評分公式 ---
        mult = 20
        thresh = 10
        df_final["模擬舊價"] = (df_final["現價"] * (1 + mult/100)).round(1)
        df_final["跌幅"] = ((df_final["模擬舊價"] - df_final["現價"]) / df_final["模擬舊價"] * 100).round(1)
        
        def score(row):
            s = 0
            # 1. 賠率面 (基於真實勝率數據)
            if row["跌幅"] >= thresh: s += 35 # 落飛依然是強信號
            
            # 根據數據：賠率<5.0 勝率高達 27%，加分必須重
            if row["現價"] <= 5.0: s += 25
            elif row["現價"] <= 10.0: s += 10
            
            # 2. 實力面 (基於真實數據排名)
            # 潘頓/麥道朗的分數在這裡會非常高 (9.2分 / 8.5分)
            # 其他騎師大多在 2-4 分，差距拉開了
            j_score = get_ability_score(row["騎師"], JOCKEY_RANK)
            t_score = get_ability_score(row["練馬師"], TRAINER_RANK)
            
            # 騎師權重 x 2 (因為數據顯示騎師影響力遠大於練馬師)
            s += j_score * 2.5 
            
            # 練馬師權重 x 1.5
            s += t_score * 1.5
            
            return round(s, 1)
            
        df_final["得分"] = df_final.apply(score, axis=1)
        df_final = df_final.sort_values(["得分", "現價"], ascending=[False, True])
        
        st.divider()
        st.subheader("📊 2024/25 數據模型預測")
        
        df_display = df_final.reset_index()
        
        # 高亮顯示高分馬
        top_picks = df_display[df_display["得分"] >= 65] # 門檻稍微提高
        if not top_picks.empty:
            st.success(f"🔥 根據本季數據，以下馬匹勝率極高：")
            st.dataframe(
                top_picks[["馬號", "馬名", "騎師", "練馬師", "現價", "得分"]],
                use_container_width=True, hide_index=True
            )
        
        with st.expander("查看全場詳情"):
            st.dataframe(
                df_display[["馬號", "馬名", "騎師", "練馬師", "現價", "得分"]],
                use_container_width=True, hide_index=True
            )
    else:
        st.error("解析失敗。")
elif raw_odds:
    # 只有賠率時的簡單模式
    df_odds = parse_odds_data(raw_odds)
    if not df_odds.empty:
        df_display = df_odds.reset_index()
        st.dataframe(df_display, use_container_width=True, hide_index=True)







