import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.46 (Stable Card + Info Odds) =====================
# 排位表：維持 V1.41 邏輯 (racing.hkjc.com) -> 您的最愛
# 賠率表：改用 racing.hkjc.com 的 Odds 頁面，但加上強力偽裝 Header

st.set_page_config(page_title="賽馬智腦 V1.46", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 1. 排位表抓取 (鎖定 V1.41 邏輯) -----------------
def fetch_race_card_stable(date_str, race_no):
    """
    從 racing.hkjc.com 資訊網抓取排位表 (已驗證成功)
    """
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    log = [f"排位表連線: {url}"]
    
    try:
        # 這裡不需要太複雜的 Header，因為資訊網排位表通常公開
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        # 轉碼處理，防止中文亂碼
        resp.encoding = 'utf-8' 
        
        dfs = pd.read_html(resp.text)
        target_df = pd.DataFrame()
        max_rows = 0
        
        for df in dfs:
            # 清理欄位
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            if len(df) > max_rows and ('馬名' in df.columns or '馬號' in df.columns):
                target_df = df
                max_rows = len(df)
        
        if not target_df.empty:
            log.append(f"成功鎖定排位表，共 {len(target_df)} 匹")
            if '馬號' in target_df.columns:
                target_df['馬號'] = pd.to_numeric(target_df['馬號'], errors='coerce')
            return target_df, "\n".join(log)
            
        return pd.DataFrame(), "\n".join(log) + "\n錯誤: 找不到排位表格"

    except Exception as e:
        return pd.DataFrame(), "\n".join(log) + f"\n排位表錯誤: {str(e)}"

# ----------------- 2. 賠率抓取 (Web Scraping 強化版) -----------------
def fetch_odds_from_info_site(date_str, race_no):
    """
    嘗試從 racing.hkjc.com 的 Odds 頁面抓取
    網址: WinPlaceAndWB.aspx
    """
    # 必須嘗試兩個場地，因為我們不知道是 HV 還是 ST
    # 為了節省時間，根據星期幾猜測
    dt = datetime.strptime(date_str, "%Y/%m/%d")
    # 週三=HV, 其他=ST (先猜)
    venue = "HV" if dt.weekday() == 2 else "ST"
    
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/Odds/WinPlaceAndWB.aspx?RaceDate={date_str}&Racecourse={venue}&RaceNo={race_no}"
    
    log = [f"賠率頁面連線: {url}"]
    
    try:
        # 強力偽裝 Header
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx"
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        
        if "沒有相符的資料" in resp.text:
            log.append("官方回傳無賠率資料 (可能尚未開盤或場地錯誤)")
            return {}, "\n".join(log)

        dfs = pd.read_html(resp.text)
        odds_map = {}
        found = False
        
        for df in dfs:
            # 清理欄位，處理 MultiIndex
            new_cols = []
            for col in df.columns:
                c_str = "".join([str(x) for x in col]) if isinstance(col, tuple) else str(col)
                new_cols.append(c_str)
            df.columns = new_cols
            
            # 尋找包含 "獨贏" 和 "馬號" 的表格
            has_win = any("獨贏" in c or "Win" in c for c in df.columns)
            has_no = any("馬號" in c or "No." in c for c in df.columns)
            
            if has_win and has_no:
                found = True
                log.append(f"找到賠率表，欄位: {list(df.columns)}")
                
                # 找出對應欄位名稱
                no_col = next(c for c in df.columns if "馬號" in c or "No." in c)
                win_col = next(c for c in df.columns if "獨贏" in c or "Win" in c)
                
                # 建立對照表
                for idx, row in df.iterrows():
                    try:
                        h_no = int(row[no_col])
                        h_odds = row[win_col]
                        # 處理 "SCR" 或 "-"
                        if str(h_odds).strip() == "-" or "SCR" in str(h_odds):
                            odds_map[h_no] = "退出"
                        else:
                            odds_map[h_no] = h_odds
                    except:
                        continue
                break
        
        if found:
            return odds_map, "\n".join(log)
        else:
            log.append("未找到賠率表格 (可能尚未開盤)")
            return {}, "\n".join(log)

    except Exception as e:
        log.append(f"賠率抓取錯誤: {str(e)}")
        return {}, "\n".join(log)

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.46 (穩定排位 + 網頁賠率)")

now = datetime.now(HKT)
# 智能預設日期：週二抓明天，其他抓今天
if now.weekday() == 1:
    def_date = (now + timedelta(days=1)).strftime("%Y/%m/%d")
    st.info("💡 系統檢測到今天是週二，預設抓取 **明天 (週三)** 的賽事。")
else:
    def_date = now.strftime("%Y/%m/%d")

col1, col2 = st.columns([1, 2])

with col1:
    date_in = st.text_input("日期 (YYYY/MM/DD)", value=def_date)
    race_in = st.number_input("場次", 1, 14, 1)
    
    if st.button("🚀 獲取數據", type="primary"):
        with st.status("執行中...", expanded=True) as status:
            # 1. 抓排位
            st.write("正在下載排位表...")
            df, log_card = fetch_race_card_stable(date_in, race_in)
            
            if not df.empty:
                # 2. 抓賠率
                st.write("排位表 OK，正在切換頁面抓取賠率...")
                odds_map, log_odds = fetch_odds_from_info_site(date_in, race_in)
                
                # 3. 合併
                if odds_map:
                    st.write("賠率表 OK，合併數據...")
                    df["獨贏"] = df["馬號"].map(odds_map).fillna("未開盤")
                else:
                    st.write("賠率尚未開盤，僅顯示排位。")
                    df["獨贏"] = "未開盤"
                
                st.session_state['df_146'] = df
                st.session_state['log_146'] = log_card + "\n\n" + log_odds
                status.update(label="完成", state="complete")
            else:
                st.session_state['log_146'] = log_card
                status.update(label="失敗：無法下載排位表", state="error")

with col2:
    if 'df_146' in st.session_state:
        df = st.session_state['df_146']
        
        st.subheader(f"第 {race_in} 場賽事")
        
        # 顯示
        # 根據實際欄位動態調整
        base_cols = ['馬號', '馬名', '獨贏', '騎師', '練馬師', '檔位', '排位體重', '評分']
        final_cols = [c for c in base_cols if c in df.columns]
        
        st.dataframe(
            df[final_cols], 
            use_container_width=True, 
            hide_index=True
        )
        
        with st.expander("系統日誌"):
            st.text(st.session_state['log_146'])
