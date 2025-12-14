import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="HKJC 智能馬經", layout="wide")
st.title("🏇 HKJC 智能投注建議系統")
st.caption("新手友善版：自動分析落飛信號，提供明確買入建議。")

raw_text = st.text_area("請在此貼上賠率表數據：", height=300, placeholder="貼上馬號、馬名、賠率...")

# 解析函數 (保持不變，負責抓數據)
def parse_with_name(text):
    rows = []
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    i = 0
    while i < len(lines):
        try:
            line1 = lines[i]
            if re.match(r'^\d+$', line1):
                horse_no = int(line1)
                horse_name = "未知"
                win_odds = 0.0
                if i+1 < len(lines): horse_name = lines[i+1]
                if i+2 < len(lines):
                    nums = re.findall(r'\d+\.?\d*', lines[i+2])
                    if nums:
                        win_odds = float(nums[0])
                        rows.append({"馬號": horse_no, "馬名": horse_name, "現價": win_odds})
                        i += 3
                        continue
            i += 1
        except: i += 1
    if rows:
        return pd.DataFrame(rows).drop_duplicates(subset=["馬號"], keep="last").sort_values("馬號")
    return pd.DataFrame()

if raw_text:
    df = parse_with_name(raw_text)
    
    if not df.empty:
        st.divider()
        
        # 隱藏的參數設定 (新手不需要看太多參數，用預設值即可)
        with st.expander("⚙️ 進階參數設定 (點擊展開)"):
            c1, c2 = st.columns(2)
            mult = c1.slider("模擬冷熱變動幅度 (%)", 0, 50, 20) # 預設調高一點，更嚴格
            thresh = c2.slider("落飛門檻 (%)", 0, 30, 10)     # 預設 10%，只抓顯著落飛
        
        # 計算核心數據
        df["模擬舊價"] = (df["現價"] * (1 + mult/100)).round(1)
        df["跌幅"] = ((df["模擬舊價"] - df["現價"]) / df["模擬舊價"] * 100).round(1)
        
        # ================= 智能分析邏輯 =================
        def analyze_horse(row):
            odds = row["現價"]
            drop = row["跌幅"]
            
            if odds == 0: return "🚫", "退出", "無", 0
            
            # 勝率估算 (簡單模型：1/賠率 * 0.85 回報率扣除)
            win_prob = round((1 / odds) * 80, 1) if odds > 0 else 0
            
            rec_level = "⚪" # 預設無推薦
            strategy = "觀望"
            risk = "中"
            
            # 策略判定
            if drop >= thresh: # 有落飛支持
                if odds <= 5.0:
                    rec_level = "⭐⭐⭐"
                    strategy = "🔥 重注獨贏 (Win)"
                    risk = "低 (穩健)"
                elif odds <= 10.0:
                    rec_level = "⭐⭐"
                    strategy = "💰 獨贏+位置 (W+P)"
                    risk = "中 (值博)"
                elif odds <= 20.0:
                    rec_level = "⭐"
                    strategy = "🎲 小注博冷"
                    risk = "高 (冷門)"
                else:
                    rec_level = "⚠️"
                    strategy = "觀察 (過冷)"
                    risk = "極高"
            else:
                # 沒落飛，但賠率極熱 (大熱門)
                if odds <= 3.0:
                    rec_level = "⭐"
                    strategy = "防守性位置 (Place)"
                    risk = "低"
            
            return rec_level, strategy, risk, win_prob

        # 應用分析
        df[["推薦度", "投注建議", "風險等級", "勝率預估(%)"]] = df.apply(
            lambda x: pd.Series(analyze_horse(x)), axis=1
        )
        
        # 過濾：只顯示有推薦的馬，或者全部顯示
        # 為了新手方便，我們把「推薦度」高的排前面
        df_sorted = df.sort_values(by=["推薦度", "現價"], ascending=[False, True])
        
        # 顯示重點推薦 (置頂)
        top_picks = df_sorted[df_sorted["推薦度"].str.contains("⭐")]
        
        if not top_picks.empty:
            st.subheader("🏆 重點推薦馬匹 (新手直接看這裡)")
            st.info("💡 跟買策略：優先考慮「⭐⭐⭐」的馬匹。若無，則考慮「⭐⭐」。")
            st.dataframe(
                top_picks[["馬號", "馬名", "現價", "推薦度", "投注建議", "風險等級", "勝率預估(%)"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("⚠️ 本場賽事暫無顯著「落飛」馬匹，建議忍手或小注怡情。")

        # 顯示完整清單
        with st.expander("查看所有馬匹詳情"):
            st.dataframe(
                df_sorted[["馬號", "馬名", "現價", "跌幅", "推薦度", "投注建議"]],
                use_container_width=True,
                hide_index=True
            )
            
    else:
        st.error("無法識別數據，請確認複製格式正確。")



