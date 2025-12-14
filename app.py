import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (專用版)")

st.caption("針對排列格式：馬號 | 膽 | 腳 | 馬名 | 獨贏 | 位置")

raw_text = st.text_area("貼上表格數據：", height=300)

def parse_special_format(text):
    rows = []
    lines = text.strip().split('\n')
    
    for line in lines:
        # 用空白切割一行
        parts = re.split(r'\s+', line.strip())
        
        # 至少要有 4-5 個部分才算是一行完整的數據
        # 例如: "1  口  口  飛躍精英  12.0  3.5"
        if len(parts) < 4:
            continue
            
        try:
            # 1. 抓馬號 (通常是第一個)
            p_no = parts[0]
            if not p_no.isdigit(): continue
            horse_no = int(p_no)
            if horse_no > 24: continue
            
            # 2. 抓獨贏賠率
            # 邏輯：從後面數回來
            # 最後一個 parts[-1] 應該是 位置賠率 (如 3.5)
            # 倒數第二個 parts[-2] 應該是 獨贏賠率 (如 12.0)
            
            # 先找所有像是賠率的數字 (包含小數點)
            odds_candidates = []
            for p in parts:
                clean_p = re.sub(r'[^\d\.]', '', p) # 去除箭頭等符號
                if re.match(r'^\d+\.\d+$', clean_p):
                    odds_candidates.append(float(clean_p))
                elif "SCR" in p: # 退出
                    odds_candidates.append(0.0)
            
            # 如果這一行裡有找到至少兩個賠率 (獨贏 + 位置)
            if len(odds_candidates) >= 2:
                # 獨贏通常是「倒數第二個」數字
                # 位置通常是「倒數第一個」數字
                # (有些馬可能只有獨贏沒位置，那列表長度可能只有1，要小心)
                
                win_odds = odds_candidates[-2] # 取倒數第二個
                
                # 簡單防呆：如果取到的賠率超級大 (比如不小心抓到投注額)，可能要濾掉
                # 但賽馬賠率幾百倍都有可能，先不設限
                
                rows.append({"HorseNo": horse_no, "Odds": win_odds})
                
            elif len(odds_candidates) == 1:
                # 只有一個賠率，那大概率就是獨贏 (或位置沒開盤)
                rows.append({"HorseNo": horse_no, "Odds": odds_candidates[0]})
                
        except:
            continue
            
    if rows:
        df = pd.DataFrame(rows)
        return df.drop_duplicates(subset=["HorseNo"], keep="last").sort_values("HorseNo")
    return pd.DataFrame()

if raw_text:
    df = parse_special_format(raw_text)
    
    if not df.empty:
        st.success(f"成功抓到 {len(df)} 隻馬！")
        
        # 顯示原始抓取結果讓您核對
        with st.expander("🔍 點擊核對抓到的賠率是否正確"):
            st.dataframe(df.T) # 轉置顯示比較好對

        st.divider()
        c1, c2 = st.columns(2)
        mult = c1.slider("變動(%)", 0, 50, 15)
        thresh = c2.slider("門檻(%)", 0, 30, 5)
        
        df["Last"] = df["Odds"]
        df["First"] = (df["Odds"] * (1 + mult/100)).round(1)
        df["Drop"] = ((df["First"] - df["Last"]) / df["First"] * 100).round(1)
        
        def sig(row):
            if row["Last"] == 0: return "退出"
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
        st.error("解析失敗。請確認貼上的文字格式包含馬號和兩個賠率數字。")


