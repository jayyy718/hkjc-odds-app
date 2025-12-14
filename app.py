import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析")
st.caption("支援格式：馬號(換行) -> 馬名(換行) -> 賠率(換行)")

raw_text = st.text_area("請在此貼上表格數據：", height=400)

def parse_with_name(text):
    rows = []
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    i = 0
    while i < len(lines):
        try:
            line1 = lines[i] # 預期是馬號
            
            # 判斷是否為馬號 (純數字)
            if re.match(r'^\d+$', line1):
                horse_no = int(line1)
                
                # 假設結構是：
                # i   : 馬號
                # i+1 : 馬名 (安都)
                # i+2 : 賠率 (4.9 2.3)
                
                horse_name = "未知"
                win_odds = 0.0
                
                # 嘗試抓馬名
                if i+1 < len(lines):
                    # 馬名通常不包含數字 (除了個別特殊的)
                    horse_name = lines[i+1]
                
                # 嘗試抓賠率
                if i+2 < len(lines):
                    odds_line = lines[i+2]
                    # 抓出賠率數字
                    nums = re.findall(r'\d+\.?\d*', odds_line)
                    if nums:
                        win_odds = float(nums[0]) # 取第一個數字為獨贏
                        
                        rows.append({
                            "馬號": horse_no,
                            "馬名": horse_name,
                            "現價": win_odds
                        })
                        i += 3 # 跳過這三行，繼續找下一匹
                        continue
            
            i += 1
                
        except:
            i += 1
            
    if rows:
        df = pd.DataFrame(rows)
        return df.drop_duplicates(subset=["馬號"], keep="last").sort_values("馬號")
    return pd.DataFrame()

if raw_text:
    df = parse_with_name(raw_text)
    
    if not df.empty:
        st.success(f"成功識別 {len(df)} 匹馬！")
        
        st.divider()
        c1, c2 = st.columns(2)
        mult = c1.slider("模擬冷熱變動幅度 (%)", 0, 50, 15)
        thresh = c2.slider("落飛門檻 (%)", 0, 30, 5)
        
        # 計算欄位
        df["模擬舊價"] = (df["現價"] * (1 + mult/100)).round(1)
        df["跌幅(%)"] = ((df["模擬舊價"] - df["現價"]) / df["模擬舊價"] * 100).round(1)
        
        def sig(row):
            if row["現價"] == 0: return "退出"
            if row["現價"] <= 10 and row["跌幅(%)"] > thresh:
                return "🔥 強力落飛" if row["模擬舊價"] > 10 else "✅ 一般落飛"
            return ""
            
        df["信號"] = df.apply(sig, axis=1)
        
        # 顯示全中文表格
        st.dataframe(
            df[["馬號", "馬名", "現價", "跌幅(%)", "信號"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("解析失敗。請確認複製內容包含：馬號、馬名、賠率。")



