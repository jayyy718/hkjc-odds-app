import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.43 (Venue Fix + Fuzzy Column Match) =====================
# 針對「明明有賠率卻抓不到」的問題進行修復
# 1. 強制加入 Racecourse (HV/ST) 參數
# 2. 對賠率欄位進行模糊匹配 (解決多層標題問題)

st.set_page_config(page_title="賽馬智腦 V1.43", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 輔助函數 -----------------
def get_default_settings():
    """預設時間與場地"""
    now = datetime.now(HKT)
    # 預設抓明天
    target = now + timedelta(days=1) if now.weekday() == 1 else now
    # 判斷場地：週三通常是 HV，週六日通常是 ST
    venue = "HV" if target.weekday() == 2 else "ST"
    return target.strftime("%Y/%m/%d"), venue

def clean_columns(df):
    """清理 Pandas 讀取到的混亂欄位名稱"""
    new_cols = []
    for col in df.columns:
        # 如果是多層索引 (MultiIndex)，合併成字串
        if isinstance(col, tuple):
            c_str = "".join([str(x) for x in col])
        else:
            c_str = str(col)
        # 移除空格和換行
        c_str = c_str.replace(" ", "").replace("\r", "").replace("\n", "")
        new_cols.append(c_str)
    df.columns = new_cols
    return df

def fetch_odds_robust(date_str, race_no, venue):
    """抓取賠率表 (容錯版)"""
    # 網址加入 Racecourse 參數
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/Odds/WinPlaceAndWB.aspx?RaceDate={date_str}&Racecourse={venue}&RaceNo={race_no}"
    
    log = [f"連線: {url}"]
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        
        # 檢查是否轉向到無資料頁面
        if "沒有相符的資料" in resp.text:
            return pd.DataFrame(), "\n".join(log) + "\n官方回傳: 無此場次資料 (請檢查日期/場地)"

        dfs = pd.read_html(resp.text)
        
        # 尋找賠率表
        target_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            df = clean_columns(df)
            # 賠率表通常有 '馬號' 和 '馬名'
            if len(df) > max_rows and ('馬號' in str(df.columns) or 'Horse' in str(df.columns)):
                target_df = df
                max_rows = len(df)
        
        if not target_df.empty:
            log.append(f"找到表格，欄位: {list(target_df.columns)}")
            
            # 尋找關鍵欄位 (模糊搜尋)
            win_col = None
            place_col = None
            no_col = None
            
            for c in target_df.columns:
                if "馬號" in c or "No." in c: no_col = c
                if "獨贏" in c or "Win" in c: win_col = c
                if "位置" in c or "Place" in c: place_col = c
            
            # 重新命名欄位以便合併
            rename_map = {}
            if no_col: rename_map[no_col] = "馬號"
            if win_col: rename_map[win_col] = "獨贏"
            if place_col: rename_map[place_col] = "位置"
            
            target_df = target_df.rename(columns=rename_map)
            
            # 確保有抓到「獨贏」
            if "獨贏" in target_df.columns:
                return target_df, "\n".join(log)
            else:
                log.append("⚠️ 警告: 表格中找不到『獨贏』相關欄位，可能馬會改了標題")
                return target_df, "\n".join(log)
        
        return pd.DataFrame(), "\n".join(log) + "\n找不到賠率表格"
        
    except Exception as e:
        return pd.DataFrame(), "\n".join(log) + f"\n錯誤: {str(e)}"

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.43 (診斷修復版)")

def_date, def_venue = get_default_settings()

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 🔧 參數設定")
    date_input = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    venue_input = st.radio("場地 (Venue)", ["HV (跑馬地)", "ST (沙田)"], index=0 if def_venue=="HV" else 1, horizontal=True)
    race_no = st.number_input("場次", 1, 14, 1)
    
    venue_code = "HV" if "HV" in venue_input else "ST"
    
    if st.button("🔍 抓取賠率", type="primary"):
        with st.spinner("正在解析..."):
            df, log = fetch_odds_robust(date_input, race_no, venue_code)
            st.session_state['df_143'] = df
            st.session_state['log_143'] = log

with col2:
    if 'df_143' in st.session_state:
        df = st.session_state['df_143']
        log = st.session_state['log_143']
        
        if not df.empty:
            # 檢查是否有賠率
            if "獨贏" in df.columns:
                st.success(f"成功抓取第 {race_no} 場賠率！")
                
                # 簡單排序 (如果獨贏是數字)
                try:
                    df["SortKey"] = pd.to_numeric(df["獨贏"], errors='coerce').fillna(999)
                    df = df.sort_values("SortKey")
                except: pass
                
                st.dataframe(
                    df[["馬號", "馬名", "獨贏", "位置"]], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("抓到了表格，但找不到『獨贏』欄位。請查看下方原始資料。")
                st.write(df)
        else:
            st.error("抓取失敗")
            
        with st.expander("🛠️ 除錯日誌 (Debug Log)"):
            st.text(log)
            st.caption("如果官方回傳無資料，請嘗試切換場地 (HV/ST)。")
