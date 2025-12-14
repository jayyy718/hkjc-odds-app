import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC 智能分析", layout="wide")
st.title("🏇 HKJC 全方位智能分析系統")
st.caption("結合：賠率落飛 + 騎師實力 + 馬匹基本面 = 最高勝率預測")

# ===================== 1. 內建騎師/練馬師實力庫 =====================
# 這裡簡單定義：分數越高越強 (基於長期勝率)
JOCKEY_RANK = {
    "潘頓": 10, "布文": 9, "麥道朗": 9.5, "田泰安": 8, "何澤堯": 8.5,
    "鍾易禮": 7, "艾道拿": 8, "希威森": 7.5, "巴度": 7, "班德禮": 7.5,
    "周俊樂": 6, "楊明綸": 5, "巫顯東": 4, "賀銘年": 6, "蔡明紹": 7
}

TRAINER_RANK = {
    "伍鵬志": 9, "呂健威": 9, "姚本輝": 8.5, "蔡約翰": 9.5, "告東尼": 9,
    "沈集成": 8.5, "方嘉柏": 8, "羅富全": 8, "大衛希斯": 8, "韋達": 7.5
}

def get_ability_score(name, rank_dict):
    # 如果名字在名單內，返回分數，否則返回預設值 6
    for key in rank_dict:
        if key in name:
            return rank_dict[key]
    return 6.0

# ===================== 2. 數據輸入區 =====================
col_input1, col_input2 = st.columns(2)

with col_input1:
    raw_odds = st.text_area("1️⃣ 貼上「賠率表」文字 (必填)：", height=200, placeholder="包含：馬號、馬名、賠率...")

with col_input2:
    raw_info = st.text_area("2️⃣ 貼上「排位表」文字 (選填)：", height=200, placeholder="包含：馬號、馬名、騎師、練馬師...")
    st.caption("提示：若不貼排位表，將只分析賠率。排位表可從馬會或馬經網站複製。")

# ===================== 3. 解析函數 =====================
def parse_odds_data(text):
    """解析賠率數據"""
    rows = []
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    i = 0
    while i < len(lines):
        try:
            if re.match(r'^\d+$', lines[i]):
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
            i += 1
        except: i += 1
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

def parse_info_data(text):
    """解析排位表數據 (抓騎師/練馬師)"""
    rows = []
    lines = text.strip().split('\n')
    for line in lines:
        # 簡單解析：嘗試在一行內找到馬號、騎師名
        # 假設格式: 1  飛躍精英  潘頓  呂健威
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            no = int(parts[0])
            # 簡單搜尋騎師名字
            jockey = "未知"
            trainer = "未知"
            
            for part in parts:
                # 檢查是否為騎師
                for j_name in JOCKEY_RANK.keys():
                    if j_name in part: jockey = j_name
                # 檢查是否為練馬師
                for t_name in TRAINER_RANK.keys():
                    if t_name in part: trainer = t_name
            
            rows.append({"馬號": no, "騎師": jockey, "練馬師": trainer})
    
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

# ===================== 4. 主邏輯 =====================
if raw_odds:
    # 1. 處理賠率
    df_odds = parse_odds_data(raw_odds)
    
    # 2. 處理排位資料 (如果有)
    df_info = pd.DataFrame()
    if raw_info:
        df_info = parse_info_data(raw_info)
    
    if not df_odds.empty:
        # 合併資料
        if not df_info.empty:
            df_final = df_odds.join(df_info, how="left")
            df_final["騎師"] = df_final["騎師"].fillna("未知")
            df_final["練馬師"] = df_final["練馬師"].fillna("未知")
        else:
            df_final = df_odds
            df_final["騎師"] = "未知"
            df_final["練馬師"] = "未知"
        
        # 3. 計算落飛 (資金流)
        mult = 20 # 模擬變動幅度
        thresh = 10 # 落飛門檻
        df_final["模擬舊價"] = (df_final["現價"] * (1 + mult/100)).round(1)
        df_final["跌幅(%)"] = ((df_final["模擬舊價"] - df_final["現價"]) / df_final["模擬舊價"] * 100).round(1)
        
        # 4. 綜合評分系統 (核心演算法)
        def calculate_score(row):
            score = 0
            reasons = []
            
            # A. 資金面 (最高 50分)
            if row["跌幅(%)"] >= thresh:
                score += 40
                reasons.append("🔥大幅落飛")
            elif row["跌幅(%)"] >= 5:
                score += 20
                reasons.append("💰微幅落飛")
            
            if row["現價"] <= 5.0:
                score += 10
                reasons.append("🔥大熱門")
            
            # B. 人強馬壯面 (最高 50分)
            j_score = get_ability_score(row["騎師"], JOCKEY_RANK)
            t_score = get_ability_score(row["練馬師"], TRAINER_RANK)
            
            # 騎師加分
            if j_score >= 9:
                score += 20
                reasons.append(f"👨‍✈️頂級騎師({row['騎師']})")
            elif j_score >= 8:
                score += 10
            
            # 練馬師加分
            if t_score >= 9:
                score += 15
                reasons.append(f"🏠冠軍馬房({row['練馬師']})")
            
            # 騎練組合加成 (名師名將)
            if j_score >= 9 and t_score >= 9:
                score += 15
                reasons.append("✨黃金組合")
                
            return score, ", ".join(reasons)

        df_final[["綜合得分", "推薦理由"]] = df_final.apply(
            lambda x: pd.Series(calculate_score(x)), axis=1
        )
        
        # 5. 產生最終建議
        def get_final_advice(score):
            if score >= 80: return "⭐⭐⭐ 全力出擊 (Win)"
            if score >= 60: return "⭐⭐ 值得一試 (Win/Place)"
            if score >= 40: return "⭐ 小注防守"
            return "觀望"
            
        df_final["最終建議"] = df_final["綜合得分"].apply(get_final_advice)
        
        # 排序：得分高 -> 賠率低
        df_final = df_final.sort_values(by=["綜合得分", "現價"], ascending=[False, True]).reset_index()
        
        # ===================== 5. 顯示結果 =====================
        st.divider()
        st.subheader("🏆 AI 智能預測結果")
        
        # 只顯示值得買的
        good_horses = df_final[df_final["綜合得分"] >= 60]
        
        if not good_horses.empty:
            st.success("發現高勝率機會！建議關注以下馬匹：")
            st.dataframe(
                good_horses[["馬號", "馬名", "騎師", "現價", "最終建議", "綜合得分", "推薦理由"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("本場賽事形勢混亂，無特別高分馬匹，建議忍手。")
            
        with st.expander("查看全場詳細數據"):
            st.dataframe(df_final)
            
    else:
        st.error("賠率表解析失敗，請重新複製。")



