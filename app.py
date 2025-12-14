import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (萬能版)")

st.caption("使用說明：全選網頁文字 -> 複製 -> 貼上")

def parse_text_loose(raw_text):
    """
    超級寬鬆解析模式：不看行，只看數字序列。
    假設數據流是：馬號 -> (文字) -> 賠率 -> 馬號 -> (文字) -> 賠率...
    """
    # 1. 預處理：把所有非數字、非小數點、非文字的符號都變成空格
    # 保留中文、英文、數字、小數點
    clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\.]', ' ', raw_text)
    
    # 2. 切割成 token
    tokens = clean_text.split()
    
    rows = []
    current_horse_no = None
    
    for token in tokens:
        # 嘗試解析為數字
        if re.match(r'^\d+$', token): # 純整數 (可能是馬號)
            val = int(token)
            if 0 < val <= 24: # 合理的馬號範圍
                current_horse_no = val
                
        elif re.match(r'^\d+\.\d+$', token): # 小數點數字 (可能是賠率)
            val = float(token)
            if current_horse_no is not None:
                # 找到了一組 (馬號, 賠率)
                # 檢查賠率是否合理 (例如大於 1.0)
                if val >= 1.0:
                    rows.append({
                        "HorseNo": current_horse_no,
                        "Odds": val
                    })
                    # 找到了賠率後，重置馬號，等待下一個整數
                    current_horse_no = None
    
    if rows:
        df = pd.DataFrame(rows)
        # 去重：如果同一個馬號抓到多次，通常最後一次是最新的賠率
        df = df.drop_duplicates(subset=["HorseNo"], keep="last")
        return df.sort_values("HorseNo")
        
    return pd.DataFrame()

# ===================== 主邏輯 =====================

raw_text = st.text_area("在此貼上網頁文字：", height=300)

if raw_text:
    df = parse_text_loose(raw_text)
    
    if not df.empty:
        st.success(f"成功識別 {len(df)} 匹馬！ (馬號: {df['HorseNo'].min()} - {df['HorseNo'].max()})")
        
        st.divider()
        c1, c2 = st.columns(2)
        mult = c1.slider("變動(%)", 0, 50, 15)
        thresh = c2.slider("門檻(%)", 0, 30, 5)
        
        df["Last"] = df["Odds"]
        df["First"] = (df["Odds"] * (1 + mult/100)).round(1)
        df["Drop"] = ((df["First"] - df["Last"]) / df["First"] * 100).round(1)
        
        def sig(row):
            if row["Last"] <= 10 and row["Drop"] > thresh:
                return "🔥" if row["First"] > 10 else "✅"
            return ""
            
        df["Sig"] = df.apply(sig, axis=1)
        
        # 顯示
        st.dataframe(
            df[["HorseNo", "Last", "Drop", "Sig"]].rename(columns={"HorseNo": "馬號", "Last": "賠率", "Drop": "跌幅", "Sig": "信號"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("無法識別。請確認文字中包含數字格式的賠率 (如 5.4)。")

