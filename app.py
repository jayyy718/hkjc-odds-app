import streamlit as st
import pandas as pd
import re

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC 落飛分析 (文字複製版)", layout="wide")

st.title("🏇 HKJC 落飛分析 (文字複製版)")
st.caption("最簡單的方法：直接從馬會網頁複製賠率表貼上即可。")

# ===================== 側邊欄 =====================
st.sidebar.header("⚙️ 設定")
race_no = st.sidebar.number_input("場次 (Race)", 1, 14, 1)

# ===================== 核心解析函數 =====================
def parse_copied_text(raw_text):
    """
    智能解析：從雜亂的複製文字中提取 馬號、馬名、賠率
    支援格式：
    1  馬名  10.0
    2  馬名  5.4
    """
    rows = []
    # 每一行處理
    lines = raw_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 嘗試用正則表達式抓取： [數字] [文字] [數字]
        # 例如: "1 飛躍精英 12.0"
        # 排除掉 "SCR" (退出馬)
        if "SCR" in line: continue
        
        try:
            # 模式 A: 簡單的 "1 馬名 9.9"
            # 匹配：開頭數字(馬號) + 空白 + 中/英文字(馬名) + 空白 + 數字(賠率)
            match = re.search(r'^(\d+)\s+([^\d]+?)\s+(\d+\.?\d*)$', line)
            
            # 模式 B: 馬會網頁複製出來的格式，有時賠率會在馬名後面很遠，或者分行
            # 這裡用一個寬鬆策略：找行內最後一個浮點數當賠率
            if not match:
                # 找行內所有數字
                nums = re.findall(r'\d+\.\d+', line)
                if nums:
                    win_odds = float(nums[-1]) # 取最後一個小數當獨贏
                    # 找馬號 (開頭的數字)
                    no_match = re.match(r'^(\d+)', line)
                    if no_match:
                        horse_no = no_match.group(1)
                        # 馬名 = 剩下的部分，去掉數字和無效符號
                        horse_name = line.replace(horse_no, "", 1).replace(str(win_odds), "").strip()
                        
                        rows.append({
                            "HorseNo": horse_no,
                            "HorseName": horse_name,
                            "Odds_Current": win_odds
                        })
                        continue

            if match:
                rows.append({
                    "HorseNo": match.group(1),
                    "HorseName": match.group(2).strip(),
                    "Odds_Current": float(match.group(3))
                })
                
        except:
            continue
            
    return pd.DataFrame(rows)

# ===================== 主畫面 =====================

st.info("📋 *使用教學*：\n1. 去馬會網頁，全選該場賽事的賠率表 (包含馬號、馬名、獨贏賠率)。\n2. 複製 (Ctrl+C)。\n3. 貼在下方 (Ctrl+V)。")

# 提供一個馬會網頁連結方便跳轉
hkjc_url = "https://bet.hkjc.com/racing/pages/odds_wp.aspx?lang=ch"
st.markdown(f"👉 [打開馬會賠率頁]({hkjc_url})")

raw_text = st.text_area("在此貼上網頁文字：", height=200, placeholder="例如：\n1  飛躍精英  12.0\n2  金鎗六十  1.5\n...")

if raw_text:
    df = parse_copied_text(raw_text)
    
    if not df.empty:
        st.success(f"成功識別 {len(df)} 匹馬！")
        
        # --- 落飛分析邏輯 ---
        st.divider()
        st.subheader("📊 分析結果")
        
        col1, col2 = st.columns(2)
        with col1:
            odds_multiplier = st.slider("模擬冷熱變動 (%)", 0, 50, 15)
        with col2:
            drop_thresh = st.slider("落飛門檻 (%)", 0, 30, 5)
            
        df["Odds_Final"] = df["Odds_Current"]
        df["Odds_5min"] = (df["Odds_Current"] * (1 + odds_multiplier/100)).round(1)
        df["Drop_Percent"] = ((df["Odds_5min"] - df["Odds_Final"]) / df["Odds_5min"] * 100).round(1)
        
        def get_signal(row):
            if row["Odds_Final"] <= 10.0 and row["Drop_Percent"] > drop_thresh:
                return "🔥 強力落飛" if row["Odds_5min"] > 10.0 else "✅ 一般落飛"
            return ""

        df["Signal"] = df.apply(get_signal, axis=1)
        
        # 顯示結果
        st.dataframe(
            df[["HorseNo", "HorseName", "Odds_Final", "Drop_Percent", "Signal"]]
            .style.format({"Odds_Final": "{:.1f}", "Drop_Percent": "{:.1f}%"}),
            use_container_width=True
        )
        
    else:
        st.error("無法識別內容。請試著只複製「表格內容」，不要複製到網頁標題。")
