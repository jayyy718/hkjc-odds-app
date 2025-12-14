import streamlit as st
import pandas as pd
import io
import re

st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (表格模式)")

st.info("💡 請從網頁複製文字後，貼在下方。如果自動解析不對，請嘗試只複製「馬號、馬名、賠率」這幾欄。")

raw_text = st.text_area("貼上表格數據：", height=300)

def try_parse_table(text):
    rows = []
    lines = text.strip().split('\n')
    
    for line in lines:
        # 將一行文字裡的所有連續空白視為分隔符
        # 例如 "1   飛躍精英    12.0" -> ["1", "飛躍精英", "12.0"]
        parts = re.split(r'\s+', line.strip())
        
        # 我們嘗試找出這一行裡最有可能是「馬號」和「賠率」的兩個欄位
        # 策略：
        # 1. 馬號通常在開頭，是整數 (1-14)
        # 2. 賠率通常在後面，是浮點數 (如 5.6)，或者是 "SCR"
        
        horse_no = None
        odds = None
        
        # 從左邊找馬號
        for p in parts[:3]: # 只看前三個欄位
            if p.isdigit() and 1 <= int(p) <= 24:
                horse_no = int(p)
                break
                
        # 從右邊找賠率
        for p in reversed(parts): # 從後面往前找
            # 移除常見的賠率變動符號 (如 12.0▼)
            clean_p = re.sub(r'[^\d\.]', '', p)
            if re.match(r'^\d+\.\d+$', clean_p):
                odds = float(clean_p)
                break
            elif "SCR" in p: # 退出馬
                odds = 0.0
                break
        
        if horse_no is not None and odds is not None:
            rows.append({"HorseNo": horse_no, "Odds": odds})
            
    if rows:
        df = pd.DataFrame(rows)
        return df.drop_duplicates(subset=["HorseNo"], keep="last").sort_values("HorseNo")
    return pd.DataFrame()

if raw_text:
    df = try_parse_table(raw_text)
    
    if not df.empty:
        st.success(f"成功抓到 {len(df)} 隻馬！ (馬號: {df['HorseNo'].min()} - {df['HorseNo'].max()})")
        
        # 讓您檢查一下抓對沒
        with st.expander("點擊檢查抓取結果"):
            st.dataframe(df)

        st.divider()
        c1, c2 = st.columns(2)
        mult = c1.slider("變動(%)", 0, 50, 15)
        thresh = c2.slider("門檻(%)", 0, 30, 5)
        
        df["Last"] = df["Odds"]
        df["First"] = (df["Odds"] * (1 + mult/100)).round(1)
        df["Drop"] = ((df["First"] - df["Last"]) / df["First"] * 100).round(1)
        
        def sig(row):
            # 排除賠率為 0 的退出馬
            if row["Last"] == 0: return "🚫 退出"
            if row["Last"] <= 10 and row["Drop"] > thresh:
                return "🔥" if row["First"] > 10 else "✅"
            return ""
            
        df["Sig"] = df.apply(sig, axis=1)
        
        st.dataframe(
            df[["HorseNo", "Last", "Drop", "Sig"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("解析失敗。請試著：不要全選網頁，只選取表格那一塊區域複製。")


