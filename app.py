import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC 智能分析", layout="wide")
st.title("🏇 HKJC 全方位智能分析系統 (精準版)")

# ... (內建騎師/練馬師實力庫代碼保持不變) ...
# ... (為了節省篇幅，請保留 JOCKEY_RANK 和 TRAINER_RANK 的定義) ...
# (如果您需要我再貼一次這部分請告訴我)

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

# ===================== 輸入區 =====================
c1, c2 = st.columns(2)
raw_odds = c1.text_area("1. 貼上賠率表 (馬號/馬名/賠率)", height=200)
raw_info = c2.text_area("2. 貼上排位表 (馬號...馬名...騎師...練馬師)", height=200)

# ===================== 核心解析 =====================
def parse_odds_data(text):
    """解析賠率 (沿用之前的穩定版邏輯)"""
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
    """
    精準解析排位表
    格式: 馬號(1) 近績(2) 綵衣(3) 馬名(4) 負磅(5) 騎師(6) 檔位(7) 練馬師(8)...
    """
    rows = []
    lines = text.strip().split('\n')
    
    for line in lines:
        # 用空白切割
        parts = line.strip().split()
        
        # 至少要有 8 個欄位才算是一行完整的排位數據
        if len(parts) >= 8:
            # 檢查第一欄是否為數字 (馬號)
            if parts[0].isdigit():
                try:
                    no = int(parts[0])
                    
                    # 根據您提供的順序：
                    # parts[0] -> 馬號
                    # parts[1] -> 近績 (如 123456)
                    # parts[2] -> 綵衣 (可能沒有文字，或者是一串符號)
                    # parts[3] -> 馬名 (重要！)
                    # parts[4] -> 負磅 (如 135)
                    # parts[5] -> 騎師 (重要！)
                    # parts[6] -> 檔位
                    # parts[7] -> 練馬師 (重要！)
                    
                    # 注意：有時候「綵衣」那一欄如果複製成文字可能會是空的，導致位移
                    # 所以我們用一個比較保險的方法：找馬名
                    # 馬名通常是中文，且在第 3-5 個位置左右
                    
                    # 這裡我們嘗試用「相對位置」定位：
                    # 騎師通常在練馬師前面兩格
                    # 練馬師通常在評分前面
                    
                    # 簡單策略：直接取固定索引 (假設複製出來完全對應您的標題順序)
                    # 如果發現對不上，可以用正則去抓中文名字
                    
                    # 這裡假設您的複製非常標準：
                    # 1  123/456  (圖)  飛躍精英  135  潘頓  5  蔡約翰 ...
                    
                    # 考慮到 (圖) 可能不見，我們這樣抓：
                    # 馬名：第一個純中文詞
                    # 騎師：馬名後面的第二個欄位 (跳過負磅)
                    # 練馬師：騎師後面的第二個欄位 (跳過檔位)
                    
                    chn_pattern = re.compile(r'[\u4e00-\u9fa5]+')
                    chn_words = [p for p in parts if chn_pattern.match(p)]
                    
                    # 通常列表裡的中文詞順序：[馬名, 騎師, 練馬師]
                    # 有時候會有"配備"也是中文，在最後面
                    
                    if len(chn_words) >= 3:
                        horse_name = chn_words[0]
                        jockey = chn_words[1]
                        trainer = chn_words[2]
                        
                        rows.append({
                            "馬號": no,
                            "排位馬名": horse_name, # 用來核對
                            "騎師": jockey,
                            "練馬師": trainer
                        })
                except:
                    continue
                    
    return pd.DataFrame(rows).drop_duplicates(subset=["馬號"]).set_index("馬號")

# ===================== 主邏輯 =====================
if raw_odds and raw_info:
    df_odds = parse_odds_data(raw_odds)
    df_info = parse_info_data(raw_info)
    
    if not df_odds.empty and not df_info.empty:
        # 合併
        df_final = df_odds.join(df_info, how="left")
        
        # 填補漏抓的
        df_final["騎師"] = df_final["騎師"].fillna("未知")
        df_final["練馬師"] = df_final["練馬師"].fillna("未知")
        
        # --- 評分邏輯 (保持不變) ---
        mult = 20
        thresh = 10
        df_final["模擬舊價"] = (df_final["現價"] * (1 + mult/100)).round(1)
        df_final["跌幅"] = ((df_final["模擬舊價"] - df_final["現價"]) / df_final["模擬舊價"] * 100).round(1)
        
        def score(row):
            s = 0
            # 資金
            if row["跌幅"] >= thresh: s += 40
            if row["現價"] <= 5.0: s += 10
            # 實力
            j = get_ability_score(row["騎師"], JOCKEY_RANK)
            t = get_ability_score(row["練馬師"], TRAINER_RANK)
            if j >= 9: s += 20
            elif j >= 8: s += 10
            if t >= 9: s += 15
            if j >= 9 and t >= 9: s += 15
            return s
            
        df_final["得分"] = df_final.apply(score, axis=1)
        df_final = df_final.sort_values("得分", ascending=False)
        
        st.divider()
        st.subheader("📊 分析結果")
        st.dataframe(df_final[["馬號", "馬名", "騎師", "練馬師", "現價", "得分"]], use_container_width=True)
    else:
        st.error("解析失敗，請確認格式。")




