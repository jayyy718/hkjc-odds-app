import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (多行模式)")
st.caption("支援格式：馬號(換行) -> 馬名(換行) -> 賠率(換行)...")

raw_text = st.text_area("貼上表格數據：", height=400)

def parse_multiline_format(text):
    rows = []
    # 移除空行，只保留有內容的行
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    # 我們假設數據流是循環的：
    # 1. 數字 (馬號)
    # 2. 文字 (馬名)
    # 3. 數字串 (獨贏 + 位置)
    
    i = 0
    while i < len(lines):
        try:
            line1 = lines[i] # 馬號
            
            # 判斷 line1 是不是馬號 (純數字)
            if re.match(r'^\d+$', line1):
                horse_no = int(line1)
                
                # 往後看兩行
                # 有時候馬名行可能會被跳過或者有多行，所以我們主要找"賠率行"
                # 賠率行特徵：包含小數點數字 (如 4.9 2.3)
                
                # 嘗試找下一行或下兩行哪一個是賠率
                odds_line = None
                
                # 檢查 i+1 行是不是賠率
                if i+1 < len(lines) and re.search(r'\d+\.?\d*', lines[i+1]):
                    # 如果 i+1 行包含數字且不像馬名 (通常馬名不含數字)，那它可能是賠率
                    # 但這裡要小心，有些馬名帶數字。
                    # 最穩妥是：看它是否包含兩個浮點數
                    if len(re.findall(r'\d+\.\d+', lines[i+1])) >= 1:
                         odds_line = lines[i+1]
                         i += 2 # 跳過 馬號+賠率
                    else:
                         # i+1 是馬名，那 i+2 應該是賠率
                         if i+2 < len(lines):
                             odds_line = lines[i+2]
                             i += 3 # 跳過 馬號+馬名+賠率
                elif i+2 < len(lines):
                    # i+1 應該是馬名，i+2 是賠率
                    odds_line = lines[i+2]
                    i += 3
                else:
                    i += 1
                    continue

                if odds_line:
                    # 解析賠率行 "4.9   2.3"
                    # 抓出所有數字
                    nums = re.findall(r'\d+\.?\d*', odds_line)
                    
                    if nums:
                        # 第一個數字通常是獨贏
                        win_odds = float(nums[0])
                        rows.append({"HorseNo": horse_no, "Odds": win_odds})
            else:
                i += 1
                
        except:
            i += 1
            
    if rows:
        df = pd.DataFrame(rows)
        return df.drop_duplicates(subset=["HorseNo"], keep="last").sort_values("HorseNo")
    return pd.DataFrame()

if raw_text:
    df = parse_multiline_format(raw_text)
    
    if not df.empty:
        st.success(f"成功識別 {len(df)} 隻馬！")
        
        # 顯示核對表格
        with st.expander("點擊查看抓取明細"):
            st.write(df)

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
        st.error("解析失敗。請確認複製的順序是：馬號 -> 馬名 -> 賠率。")


