import streamlit as st
import pandas as pd
import re
from datetime import datetime

# ===================== 頁面設定 =====================
st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (萬能文字版)")
st.caption("解決所有連線失敗問題：直接複製網頁文字貼上即可分析！")

# ===================== 側邊欄 =====================
st.sidebar.header("設定")
st.sidebar.info("使用方法：\n1. 用手機打開賠率網頁(馬會/51saima皆可)\n2. 全選文字並複製\n3. 貼在右側輸入框")

# ===================== 萬能解析函數 =====================
def parse_text(raw_text):
    """
    強大的正則表達式解析，能從任何亂七八糟的文字中抓出馬號和賠率
    """
    rows = []
    # 預處理：將所有換行變成空格，方便正則掃描
    text = raw_text.replace("\n", "  ")
    
    # 策略 1: 尋找 "馬號 + 馬名 + 賠率" 的模式
    # 例如: "1 飛躍精英 12.0" 或 "1. 飛躍精英 12.0"
    # 正則解釋: 
    # (\d+)      -> 數字(馬號)
    # [.\s]+     -> 可能有點或空格
    # ([\u4e00-\u9fa5]+|[a-zA-Z\s]+) -> 中文或英文馬名
    # [^\d]+     -> 中間雜訊
    # (\d+\.\d+) -> 賠率(小數點)
    
    # 簡單版正則：只找 "數字 ... 小數點數字"
    # 我們假設一行裡最靠左的是馬號，最靠右的是賠率
    
    lines = raw_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 排除掉日期行、場次行
        if "場" in line and "米" in line: continue
        
        try:
            # 找行內所有數字
            # 例如 "1 飛躍精英 12.0" -> ['1', '12.0']
            # 例如 "12 飛躍精英 9.9" -> ['12', '9.9']
            
            # 使用正則提取所有數字 (包含整數和小數)
            nums = re.findall(r'\d+\.?\d*', line)
            
            if len(nums) >= 2:
                # 候選馬號：第一個數字
                no_cand = nums[0]
                # 候選賠率：最後一個數字 (且必須包含小數點，或者大於等於1.0)
                odds_cand = nums[-1]
                
                # 驗證
                if "." in odds_cand:
                    horse_no = int(float(no_cand)) # 防止 '1.0' 這種寫法
                    odds_val = float(odds_cand)
                    
                    # 過濾異常值
                    if horse_no > 0 and horse_no <= 24 and odds_val > 0:
                        # 嘗試抓馬名 (在馬號和賠率中間的文字)
                        # 這步比較難，我們簡化：直接用 '馬匹N' 代替，或者嘗試去除數字
                        temp_name = line.replace(no_cand, "", 1).replace(odds_cand, "", 1).strip()
                        # 清理馬名中的雜點
                        horse_name = re.sub(r'[^\u4e00-\u9fa5a-zA-Z]', '', temp_name)
                        if not horse_name: horse_name = f"馬匹 {horse_no}"
                        
                        rows.append({
                            "HorseNo": horse_no,
                            "HorseName": horse_name,
                            "Odds": odds_val
                        })
        except: pass
        
    # 去重 (取最後一次出現的)
    if rows:
        df = pd.DataFrame(rows)
        df = df.drop_duplicates(subset=["HorseNo"], keep="last")
        return df.sort_values("HorseNo")
        
    return pd.DataFrame()

# ===================== 主邏輯 =====================

# 連結按鈕
col_link1, col_link2 = st.columns(2)
col_link1.link_button("打開 51saima", "https://www.51saima.com/mobi/odds.jsp")
col_link2.link_button("打開 馬會賠率", "https://bet.hkjc.com/racing/pages/odds_wp.aspx?lang=ch")

# 輸入框
raw_text = st.text_area("在此貼上網頁文字 (Ctrl+V)", height=250, placeholder="請貼上複製的賠率表文字...")

if raw_text:
    df = parse_text(raw_text)
    
    if not df.empty:
        st.success(f"成功識別 {len(df)} 匹馬！")
        
        st.divider()
        col1, col2 = st.columns(2)
        mult = col1.slider("模擬冷熱變動(%)", 0, 50, 15)
        thresh = col2.slider("落飛門檻(%)", 0, 30, 5)
        
        df["Last"] = df["Odds"]
        df["First"] = (df["Odds"] * (1 + mult/100)).round(1)
        df["Drop"] = ((df["First"] - df["Last"]) / df["First"] * 100).round(1)
        
        def get_sig(row):
            if row["Last"] <= 10 and row["Drop"] > thresh:
                return "🔥" if row["First"] > 10 else "✅"
            return ""
            
        df["Sig"] = df.apply(get_sig, axis=1)
        res = df
        
        # 顯示漂亮的表格
        st.dataframe(
            res[["HorseNo", "HorseName", "Last", "Drop", "Sig"]]
            .rename(columns={"Last": "現價", "Drop": "跌幅%", "Sig": "信號"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.error("無法識別數據。請確保您複製了包含「馬號」和「賠率」的文字區塊。")

