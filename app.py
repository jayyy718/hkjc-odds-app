import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.48 (HKJC Card + STHeadline Odds) =====================
# 排位表：HKJC 資訊網 (最準確的靜態資料)
# 賠率：頭條日報 (ST Headline) (第三方媒體，較少擋 IP)

st.set_page_config(page_title="賽馬智腦 V1.48", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 排位表 (維持 V1.41 核心) -----------------
@st.cache_data(ttl=3600) # 排位表很少變，可以快取久一點
def fetch_race_card_v141(date_str, race_no):
    """從 HKJC 資訊網抓取排位"""
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
            return target_df, "HKJC 排位下載成功"
            
        return pd.DataFrame(), "錯誤: 找不到排位表"
    except Exception as e:
        return pd.DataFrame(), f"排位連線錯誤: {str(e)}"

# ----------------- 2. 即時賠率 (第三方: 頭條日報) -----------------
def fetch_odds_stheadline(date_str, race_no):
    """
    從頭條日報抓取賠率
    網址格式: https://racing.stheadline.com/racing/race-odds.php?date=2025-12-17&race_no=1
    """
    # 轉換日期格式 YYYY/MM/DD -> YYYY-MM-DD
    fmt_date = date_str.replace("/", "-")
    url = f"https://racing.stheadline.com/racing/race-odds.php?date={fmt_date}&race_no={race_no}"
    
    log = [f"第三方連線: {url}"]
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://racing.stheadline.com/"
        }
        
        resp = requests.get(url, headers=headers, timeout=8)
        # 頭條日報通常是 UTF-8，但也可能是 Big5，讓 requests 自動判斷
        resp.encoding = resp.apparent_encoding 
        
        if resp.status_code != 200:
            return {}, "\n".join(log) + f"\nHTTP 錯誤: {resp.status_code}"

        dfs = pd.read_html(resp.text)
        log.append(f"找到 {len(dfs)} 個表格")
        
        odds_map = {}
        target_df = pd.DataFrame()
        
        # 尋找賠率表
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).strip() for c in df.columns]
            
            # 頭條的賠率表通常有 "馬號" 和 "獨贏"
            if "馬號" in df.columns and "獨贏" in df.columns:
                target_df = df
                break
        
        if not target_df.empty:
            log.append("成功解析賠率表")
            # 建立對照表
            for _, row in target_df.iterrows():
                try:
                    h_no = int(row["馬號"])
                    h_win = row["獨贏"]
                    odds_map[h_no] = h_win
                except: continue
                
            return odds_map, "\n".join(log)
        else:
            return {}, "\n".join(log) + "\n錯誤: 找不到賠率欄位 (第三方可能尚未更新)"

    except Exception as e:
        return {}, "\n".join(log) + f"\n第三方解析錯誤: {str(e)}"

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.48 (第三方賠率源)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 執行設定")
    date_in = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 全自動獲取數據", type="primary"):
        with st.status("正在連線...", expanded=True) as status:
            # 1. 抓排位 (HKJC)
            st.write("1. 正在從馬會下載排位表...")
            df, msg_card = fetch_race_card_v141(date_in, race_in)
            
            if not df.empty:
                # 2. 抓賠率 (STHeadline)
                st.write("2. 正在從頭條日報獲取即時賠率...")
                odds_map, msg_odds = fetch_odds_stheadline(date_in, race_in)
                
                # 3. 合併
                if odds_map:
                    st.write("3. 數據合併中...")
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                    status.update(label="成功！", state="complete")
                else:
                    st.warning("無法從第三方獲取賠率 (可能未開盤或無資料)")
                    df["獨贏"] = "未開盤"
                    status.update(label="僅排位表 (無賠率)", state="complete")
                
                st.session_state['df_148'] = df
                st.session_state['log_148'] = msg_card + "\n\n" + msg_odds
                
            else:
                st.session_state['log_148'] = msg_card
                status.update(label="排位表下載失敗", state="error")

with col2:
    if 'df_148' in st.session_state:
        df = st.session_state['df_148']
        
        st.subheader(f"第 {race_in} 場賽事")
        
        # 檢查數據狀態
        has_odds = any(x != "未開盤" and x != "-" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 第三方賠率已更新")
        else:
            st.warning("🟡 目前僅顯示排位資料 (第三方尚未更新賠率)")
            
        # 顯示表格
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位', '排位體重']
        final_cols = [c for c in cols if c in df.columns]
        
        st.dataframe(
            df[final_cols],
            column_config={
                "獨贏": st.column_config.TextColumn("獨贏 (頭條日報)", width="medium"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        with st.expander("查看日誌"):
            st.text(st.session_state['log_148'])
