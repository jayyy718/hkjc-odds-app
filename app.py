import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta, timezone

# ===================== V1.55 (Custom Format Parser) =====================
# 專門解析格式：馬號、綵衣、馬名、檔位、負磅、騎師、練馬師、獨贏、位置...

st.set_page_config(page_title="賽馬智腦 V1.55", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 排位表下載 (不變) -----------------
@st.cache_data(ttl=600)
def fetch_race_card(date_str, race_no):
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        dfs = pd.read_html(resp.text)
        target = pd.DataFrame()
        best_len = 0
        
        for df in dfs:
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > best_len and ('馬名' in df.columns or '馬號' in df.columns):
                target = df
                best_len = len(df)
        
        if not target.empty:
            if '馬號' in target.columns:
                target['馬號'] = pd.to_numeric(target['馬號'], errors='coerce')
            return target, f"成功下載 {len(target)} 匹馬排位"
        return pd.DataFrame(), "錯誤: 找不到排位表"
    except Exception as e:
        return pd.DataFrame(), str(e)

# ----------------- 2. 定制解析器 (核心) -----------------
def parse_custom_format(text):
    """
    針對格式: [馬號] [綵衣] [馬名] [檔位] [負磅] [騎師] [練馬師] [獨贏] ...
    邏輯：
    1. 將每一行拆解成單字列表
    2. 第一個數字通常是 '馬號'
    3. 嘗試在後面的數據中尋找 '獨贏' (通常是小數點)
    """
    odds_map = {}
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 跳過標題行 (如果不小心複製到的話)
        if "馬號" in line and "獨贏" in line:
            continue
            
        # 1. 提取所有可能的數據塊 (以空格或Tab分隔)
        parts = line.split()
        
        # 至少要有 8 個部分才能對應到「獨贏」(根據您的描述)
        # 但有時候「綵衣」可能是空的，或者「獨贏及位置」是一個欄位
        # 所以我們用特徵識別比較保險
        
        if len(parts) < 3: continue
        
        try:
            # --- 步驟 A: 找馬號 ---
            # 通常是該行的第一個數字
            h_no = None
            h_idx = -1
            
            for i, p in enumerate(parts):
                if p.isdigit(): # 純數字
                    val = int(p)
                    if 1 <= val <= 14: # 合理馬號範圍
                        h_no = val
                        h_idx = i
                        break
            
            if h_no is None: continue
            
            # --- 步驟 B: 找獨贏 ---
            # 根據您的順序，獨贏在馬號後面一段距離
            # 獨贏特徵：通常包含小數點 (e.g. 2.4, 10.0)，但也可能是整數 (e.g. 10)
            # 且它不應該是檔位 (1-14) 或負磅 (100-135)
            
            h_win = None
            
            # 從馬號後面開始找
            potential_odds = parts[h_idx+1:]
            
            for p in potential_odds:
                # 排除純文字 (馬名、騎師、練馬師)
                # 排除像 "107" (負磅) 這樣的大整數
                # 排除像 "12" (檔位) 這樣的整數 (這比較難，因為賠率也可能是 12)
                
                # 判斷是否為浮點數
                if '.' in p:
                    try:
                        val = float(p)
                        # 賠率通常在 1.01 到 999 之間
                        if 1.0 < val < 500:
                            h_win = val
                            break # 找到第一個小數點數字，通常就是獨贏
                    except: pass
                
                # 如果是整數，但看起來像賠率 (例如 99)
                elif p.isdigit():
                    try:
                        val = float(p)
                        # 如果這個數字不像檔位 (例如 > 14) 且不像負磅 (< 100)
                        # 或者它出現在很後面
                        # 這邊保守一點，優先抓含小數點的。如果沒小數點，可能網站顯示格式是 10
                        # 暫時略過純整數，除非您確定網站賠率會顯示整數
                        pass 
                    except: pass
            
            if h_no and h_win:
                odds_map[h_no] = h_win
                
        except Exception:
            continue
            
    return odds_map

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.55 (定制格式版)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.info("1. 下載基礎資料")
    date_in = st.text_input("日期", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("📥 下載排位表", type="primary"):
        df, msg = fetch_race_card(date_in, race_in)
        st.session_state['df_155'] = df
        st.session_state['msg_155'] = msg
        if 'odds_155' in st.session_state: del st.session_state['odds_155']

    st.markdown("---")
    st.info("2. 貼上賠率 (全選 Ctrl+A -> 複製 Ctrl+C)")
    st.caption("格式：馬號 ... 馬名 ... 獨贏")
    
    raw_text = st.text_area("貼上區", height=200)
    
    if st.button("🔄 解析數據"):
        if raw_text:
            odds = parse_custom_format(raw_text)
            if odds:
                st.session_state['odds_155'] = odds
                st.success(f"成功抓取 {len(odds)} 筆賠率！")
            else:
                st.error("解析失敗：找不到符合格式的數據，請確認複製內容包含「馬號」與「小數點賠率」。")

with col2:
    if 'df_155' in st.session_state:
        df = st.session_state['df_155'].copy()
        
        # 整合
        if 'odds_155' in st.session_state:
            odds_map = st.session_state['odds_155']
            df["獨贏"] = df["馬號"].map(odds_map).fillna("-")
            
            # 大熱門提示
            try:
                valid = df[pd.to_numeric(df["獨贏"], errors='coerce').notnull()].copy()
                if not valid.empty:
                    valid["v"] = valid["獨贏"].astype(float)
                    valid = valid.sort_values("v")
                    best = valid.iloc[0]
                    st.success(f"🔥 大熱門：#{best['馬號']} {best['馬名']} @ {best['獨贏']}")
            except: pass
        else:
            df["獨贏"] = "等待貼上..."
            
        st.subheader(f"第 {race_in} 場排位表")
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位', '負磅']
        final = [c for c in cols if c in df.columns]
        st.dataframe(df[final], use_container_width=True, hide_index=True)
        
    elif 'msg_155' in st.session_state:
        st.error(st.session_state['msg_155'])
