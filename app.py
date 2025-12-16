import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.53 (On.cc Static Source) =====================
# 排位表：HKJC 資訊網
# 賠率：東方日報 (On.cc) - 這是靜態 HTML 檔案，最不容易失敗

st.set_page_config(page_title="賽馬智腦 V1.53", layout="wide")
HKT = timezone(timedelta(hours=8))

# --- 1. 排位表 (HKJC) ---
def fetch_card_hkjc(date_str, race_no):
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = 'utf-8'
        
        # 解析
        dfs = pd.read_html(resp.text)
        for df in dfs:
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > 5 and ('馬名' in df.columns or '馬號' in df.columns):
                if '馬號' in df.columns:
                    df['馬號'] = pd.to_numeric(df['馬號'], errors='coerce')
                return df, "HKJC 排位下載成功"
    except:
        pass
    return pd.DataFrame(), "錯誤：找不到排位表"

# --- 2. 賠率 (On.cc 東方日報) ---
def fetch_odds_oncc(date_str, race_no):
    # On.cc 網址格式: https://racing.on.cc/racing/new/YYYYMMDD/rjodds/YYYYMMDD_RaceNo.html
    # 這是一個靜態檔案，非常穩定
    
    date_compact = date_str.replace("/", "").replace("-", "") # 20251217
    url = f"https://racing.on.cc/racing/new/{date_compact}/rjodds/{date_compact}_{race_no}.html"
    
    log = [f"連線 On.cc: {url}"]
    odds_map = {}
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        
        # 關鍵：On.cc 使用 Big5 編碼，必須設定，否則亂碼
        resp.encoding = 'big5'
        
        if resp.status_code == 404:
            return {}, "\n".join(log) + "\nHTTP 404: 該場次賠率頁面尚未生成 (可能太早)"
            
        dfs = pd.read_html(resp.text)
        log.append(f"找到 {len(dfs)} 個表格")
        
        target_df = pd.DataFrame()
        
        for df in dfs:
            # On.cc 的表格通常有 "馬號" 和 "獨贏"
            # 欄位清理
            df.columns = [str(c).strip() for c in df.columns]
            
            if "馬號" in df.columns and "獨贏" in df.columns:
                target_df = df
                break
            # 有時候欄位叫 "No."
            if "No." in df.columns and "獨贏" in df.columns:
                df = df.rename(columns={"No.": "馬號"})
                target_df = df
                break

        if not target_df.empty:
            log.append("成功解析賠率表")
            for _, row in target_df.iterrows():
                try:
                    h_no = int(row["馬號"])
                    h_win = row["獨贏"]
                    # 過濾無效值
                    if str(h_win) != "-" and str(h_win) != "":
                        odds_map[h_no] = h_win
                except: pass
            
            if odds_map:
                return odds_map, "\n".join(log)
            else:
                return {}, "\n".join(log) + "\n表格解析後無數據"
        else:
            return {}, "\n".join(log) + "\n找不到符合格式的賠率表"

    except Exception as e:
        return {}, "\n".join(log) + f"\n錯誤: {str(e)}"

# --- UI ---
st.title("🏇 賽馬智腦 V1.53 (On.cc 靜態源)")

now = datetime.now(HKT)
def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d") if now.weekday() == 1 else now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    date_in = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 執行", type="primary"):
        with st.status("運行中...", expanded=True) as s:
            st.write("1. 抓取排位表 (HKJC)...")
            df, msg1 = fetch_card_hkjc(date_in, race_in)
            
            if not df.empty:
                st.write("2. 抓取賠率 (On.cc)...")
                odds_map, msg2 = fetch_odds_oncc(date_in, race_in)
                
                if odds_map:
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                    s.update(label="成功！", state="complete")
                else:
                    df["獨贏"] = "未開盤"
                    s.update(label="無賠率 (On.cc 尚未生成)", state="error")
                
                st.session_state['df_153'] = df
                st.session_state['log_153'] = msg1 + "\n\n" + msg2
            else:
                st.session_state['log_153'] = msg1
                s.update(label="排位下載失敗", state="error")

with col2:
    if 'df_153' in st.session_state:
        df = st.session_state['df_153']
        
        has_odds = any(x != "未開盤" for x in df["獨贏"])
        if has_odds:
            st.success("🟢 賠率已更新 (來源: 東方日報)")
        else:
            st.warning("🟡 暫無賠率")
            
        cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位']
        final = [c for c in cols if c in df.columns]
        
        st.dataframe(df[final], use_container_width=True, hide_index=True)
        
        with st.expander("日誌"):
            st.text(st.session_state['log_153'])
