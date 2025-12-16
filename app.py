import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone

# ===================== V1.54 (Manual Text Intelligence) =====================
# 核心理念：放棄自動連線賠率（因防火牆），改用「智能文本解析」
# 排位表：依然自動抓取 (V1.41 核心，這部分很穩定)
# 賠率：用戶「全選複製」網頁文字，程式自動提取數字

st.set_page_config(page_title="賽馬智腦 V1.54", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 自動抓取排位表 (最穩定的部分) -----------------
@st.cache_data(ttl=600)
def fetch_race_card_v141(date_str, race_no):
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        dfs = pd.read_html(resp.text)
        target_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > max_rows and ('馬名' in df.columns or '馬號' in df.columns):
                target_df = df
                max_rows = len(df)
        
        if not target_df.empty:
            if '馬號' in target_df.columns:
                target_df['馬號'] = pd.to_numeric(target_df['馬號'], errors='coerce')
            return target_df, f"排位表下載成功 (共{len(target_df)}匹)"
        return pd.DataFrame(), "錯誤: 找不到排位表格"
    except Exception as e:
        return pd.DataFrame(), f"連線錯誤: {str(e)}"

# ----------------- 2. 智能文本解析器 (核心武器) -----------------
def parse_pasted_text(text):
    """
    強大的解析器：能吃下馬會網頁、App 或任何文字
    自動尋找「馬號」與「賠率」的關聯
    """
    odds_map = {}
    lines = text.strip().split('\n')
    
    # 策略 1: 尋找標準行 "1 浪漫勇士 2.3"
    # Regex: 開頭是數字 -> 中間可能是文字 -> 結尾是小數點數字
    pattern_standard = re.compile(r'^(\d+)\s+.*?\s+(\d+\.\d+)\s*$')
    
    # 策略 2: 簡單對 (馬號, 賠率) "1 2.3"
    pattern_simple = re.compile(r'^(\d+)\s+(\d+\.\d+)\s*$')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 排除掉日期、場次等無關數字
        if "場" in line or "2025" in line or "月" in line:
            continue

        match = None
        
        # 嘗試匹配
        m1 = pattern_standard.search(line)
        if m1:
            h_no, h_odds = int(m1.group(1)), float(m1.group(2))
            if 1 <= h_no <= 14 and 1.0 <= h_odds <= 300.0: # 合理性檢查
                odds_map[h_no] = h_odds
                continue
                
        m2 = pattern_simple.search(line)
        if m2:
            h_no, h_odds = int(m2.group(1)), float(m2.group(2))
            if 1 <= h_no <= 14 and 1.0 <= h_odds <= 300.0:
                odds_map[h_no] = h_odds
                continue
        
        # 策略 3: 暴力拆解 (適用於複製了一整塊表格)
        # 找出該行所有數字
        nums = re.findall(r'\d+\.\d+|\d+', line)
        if len(nums) >= 2:
            # 假設第一個整數是馬號，最後一個浮點數是賠率
            try:
                # 找馬號 (第一個整數)
                curr_no = int(nums[0])
                # 找賠率 (倒數尋找第一個含小數點的)
                curr_odds = 0.0
                found_odds = False
                for x in reversed(nums):
                    if '.' in x:
                        curr_odds = float(x)
                        found_odds = True
                        break
                
                if found_odds and 1 <= curr_no <= 14:
                    odds_map[curr_no] = curr_odds
            except: pass

    return odds_map

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.54 (智能剪貼版)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.info("步驟 1：下載排位表")
    date_in = st.text_input("日期", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("📥 下載排位", type="primary"):
        df, msg = fetch_race_card_v141(date_in, race_in)
        st.session_state['df_154'] = df
        st.session_state['msg_154'] = msg
        # 重置賠率
        if 'odds_154' in st.session_state: del st.session_state['odds_154']

    st.markdown("---")
    st.info("步驟 2：貼上賠率文字")
    st.caption("請去馬會/頭條/App 複製賠率頁面的文字，貼在下方：")
    
    raw_text = st.text_area("在此貼上 (Ctrl+V)", height=200, placeholder="例如：\n1 號馬 3.5\n2 號馬 10.0\n...")
    
    if st.button("🔄 解析賠率"):
        if raw_text:
            odds = parse_pasted_text(raw_text)
            if odds:
                st.session_state['odds_154'] = odds
                st.success(f"成功識別 {len(odds)} 匹馬的賠率！")
            else:
                st.error("無法識別文字中的賠率，請確認內容包含「馬號」與「數字」。")

with col2:
    if 'df_154' in st.session_state:
        df = st.session_state['df_154'].copy()
        
        # 整合賠率
        if 'odds_154' in st.session_state:
            odds_map = st.session_state['odds_154']
            df["獨贏"] = df["馬號"].map(odds_map).fillna("-")
            
            # 計算推薦
            try:
                valid = df[pd.to_numeric(df["獨贏"], errors='coerce').notnull()].copy()
                if not valid.empty:
                    valid["Sort"] = valid["獨贏"].astype(float)
                    best = valid.sort_values("Sort").iloc[0]
                    st.markdown(f"""
                    <div style="background:#e8f5e9;padding:10px;border-radius:5px;border:1px solid #4caf50;color:#2e7d32;">
                        <b>🔥 賠率大熱：#{best['馬號']} {best['馬名']} ({best['獨贏']})</b>
                    </div>
                    """, unsafe_allow_html=True)
            except: pass
            
        else:
            df["獨贏"] = "等待貼上..."
            
        st.subheader(f"第 {race_in} 場排位表")
        
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final], use_container_width=True, hide_index=True)
        
    elif 'msg_154' in st.session_state:
        st.error(st.session_state['msg_154'])
    else:
        st.write("👈 請先按左上角的「下載排位」")
