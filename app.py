import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC 智能分析", layout="wide")
st.title("🏇 HKJC 全方位智能分析系統")
st.caption("結合：賠率落飛 + 騎師實力 + 馬匹基本面 = 最高勝率預測")

# ===================== 內建資料庫 =====================
JOCKEY_RANK = {
    "潘頓": 10, "布文": 9.5, "麥道朗": 9.5, "田泰安": 8, "何澤堯": 8.5,
    "鍾易禮": 7, "艾道拿": 8, "希威森": 7.5, "巴度": 7, "班德禮": 7.5,
    "周俊樂": 6, "楊明綸": 5, "巫顯東": 4, "賀銘年": 6, "蔡明紹": 7
}
TRAINER_RANK = {
    "伍鵬志": 9, "呂健威": 9, "姚本輝": 8.5, "蔡約翰": 9.5, "告東尼": 9,
    "沈集成": 8.5, "方嘉柏": 8, "羅富全": 8, "大衛希斯": 8, "韋達": 7.5
}
def get_ability_score(name, rank_dict):
    for key in rank_dict:
        if key in name: return rank_dict[key]
    return 6.0

# ===================== 輸入區 (含連結按鈕) =====================
c1, c2 = st.columns(2)

with c1:
    st.markdown("### 1️⃣ 賠率數據")
    # 51saima 連結按鈕
    st.link_button("👉 打開 51saima (賠率表)", "https://www.51saima.com/mobi/odds.jsp", use_container_width=True)
    raw_odds = st.text_area("在此貼上賠率表：", height=300, placeholder="全選複製網頁文字 -> 貼上")

with c2:
    st.markdown("### 2️⃣ 排位數據")
    # 馬會排位表連結按鈕 (通常是這個網址)
    st.link_button("👉 打開馬會 (排位表)", "https://racing.hkjc.com/racing/information/Chinese/racing/RaceCard.aspx", use_container_width=True)
    raw_info = st.text_area("在此貼上排位表：", height=300, placeholder="全選複製排位表文字 -> 貼上")

# ===================== 解析函數 =====================
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
                # 中文詞提取法
                chn_pattern = re.compile(r'[\u4e00-\u9fa5]+')
                chn_words = [p for p in parts if chn_pattern.match(p)]
                if len(chn_words) >= 3:
                    # [馬名, 騎師, 練馬師]
                    rows.append({
                        "馬號": no,
                        "騎師": chn_words[1],
                        "練馬師": chn_words[2]
                    })
            except: continue
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

# ===================== 主邏輯 =====================
if raw_odds:
    # 解析賠率
    df_odds = parse_odds_data(raw_odds)
    
    if not df_odds.empty:
        df_final = df_odds
        
        # 如果有排位表，進行合併
        if raw_info:
            df_info = parse_info_data(raw_info)
            if not df_info.empty:
                df_final = df_odds.join(df_info, how="left")
                df_final["騎師"] = df_final["騎師"].fillna("未知")
                df_final["練馬師"] = df_final["練馬師"].fillna("未知")

        # 評分邏輯
        if "騎師" not in df_final.columns:
            df_final["騎師"] = "未知"
            df_final["練馬師"] = "未知"

        mult = 20
        thresh = 10
        df_final["模擬舊價"] = (df_final["現價"] * (1 + mult/100)).round(1)
        df_final["跌幅"] = ((df_final["模擬舊價"] - df_final["現價"]) / df_final["模擬舊價"] * 100).round(1)
        
        def score(row):
            s = 0
            if row["跌幅"] >= thresh: s += 40
            if row["現價"] <= 5.0: s += 10
            
            j = get_ability_score(row["騎師"], JOCKEY_RANK)
            t = get_ability_score(row["練馬師"], TRAINER_RANK)
            
            if j >= 9: s += 20
            elif j >= 8: s += 10
            if t >= 9: s += 15
            if j >= 9 and t >= 9: s += 15
            return s
            
        df_final["得分"] = df_final.apply(score, axis=1)
        
        # 排序與顯示
        df_final = df_final.sort_values(["得分", "現價"], ascending=[False, True])
        df_display = df_final.reset_index()
        
        st.divider()
        st.subheader("📊 分析結果")
        
        # 重點推薦高分馬
        top_picks = df_display[df_display["得分"] >= 60]
        if not top_picks.empty:
            st.success(f"🔥 發現 {len(top_picks)} 匹高勝率馬！")
            st.dataframe(
                top_picks[["馬號", "馬名", "騎師", "現價", "得分"]],
                use_container_width=True,
                hide_index=True
            )
        
        with st.expander("查看全場列表"):
            st.dataframe(
                df_display[["馬號", "馬名", "騎師", "練馬師", "現價", "得分"]],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.error("賠率表解析失敗，請確認是否複製正確。")






