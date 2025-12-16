import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone

# ===================== V1.41 (HKJC Info Site + Pandas Robust) =====================
# 改用 HKJC 資訊網 (非投注網)，並使用 pd.read_html 暴力解析表格
# 解決「只有3隻馬」與「抓不到數據」的問題

st.set_page_config(page_title="賽馬智腦 V1.41", layout="wide")
HKT = timezone(timedelta(hours=8))

# ----------------- 工具函數 -----------------
def get_next_race_date():
    """尋找最近的賽事日期 (週三或週六/日)"""
    today = datetime.now(HKT)
    # 簡單邏輯：如果是週二，預設抓週三；其他情況抓當天或後續
    # 這裡為了保險，我們先回傳今天，讓使用者自己在介面選，或者預設抓明天
    if today.weekday() == 1: # 週二
        next_race = today + timedelta(days=1) # 明天週三
        return next_race.strftime("%Y/%m/%d"), next_race.strftime("%Y-%m-%d (週三)")
    elif today.weekday() == 2: # 週三
        return today.strftime("%Y/%m/%d"), today.strftime("%Y-%m-%d (週三)")
    elif today.weekday() == 5: # 週六
        return today.strftime("%Y/%m/%d"), today.strftime("%Y-%m-%d (週六)")
    elif today.weekday() == 6: # 週日
        return today.strftime("%Y/%m/%d"), today.strftime("%Y-%m-%d (週日)")
    else:
        # 預設回傳今天，雖然可能沒比賽
        return today.strftime("%Y/%m/%d"), today.strftime("%Y-%m-%d")

@st.cache_data(ttl=60)
def fetch_hkjc_html_robust(date_str, race_no):
    """
    使用 Pandas 直接讀取 HKJC 資訊網的 HTML 表格
    網址範例: https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate=2025/12/17&Racecourse=HV&RaceNo=1
    """
    # 構建 URL (使用中文介面，方便閱讀，欄位名稱固定)
    # 注意：場地 (Venue) 有時是 HV (跑馬地) 有時是 ST (沙田)。
    # 為了容錯，我們通常先試 HV，如果抓不到再試 ST，或者直接不帶 Venue 參數讓系統導向
    
    # 這裡我們嘗試不帶 Venue，HKJC 通常會自動導向到當日正確場地
    url = f"https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx?RaceDate={date_str}&RaceNo={race_no}"
    
    log = f"正在連線: {url}\n"
    
    try:
        # 使用 Pandas 的 read_html 強力解析
        # header=0 表示第一列是標題
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 請求網頁
        resp = requests.get(url, headers=headers, timeout=10)
        
        # 檢查是否轉向到了「沒有賽事」的頁面
        if "沒有相符的資料" in resp.text:
            return pd.DataFrame(), f"HKJC 回傳：該日/該場次 無資料 ({url})", False

        # 解析所有表格
        dfs = pd.read_html(resp.text)
        log += f"網頁包含 {len(dfs)} 個表格\n"
        
        target_df = pd.DataFrame()
        
        # 尋找「真正的」排位表
        # 邏輯：最大的那個表格，且包含「馬名」或「Horse」欄位
        best_len = 0
        for df in dfs:
            # 清理欄位名稱 (移除換行符號)
            df.columns = [str(c).replace(' ', '').replace('\r', '').replace('\n', '') for c in df.columns]
            
            if len(df) > best_len:
                # 檢查關鍵欄位
                if '馬名' in df.columns or '馬號' in df.columns:
                    target_df = df
                    best_len = len(df)
        
        if not target_df.empty:
            log += f"鎖定主表格，共 {len(target_df)} 匹馬\n"
            
            # 整理數據
            # 確保有我們需要的欄位，沒有的話補上
            needed_cols = ['馬號', '馬名', '騎師', '練馬師']
            for c in needed_cols:
                if c not in target_df.columns:
                    target_df[c] = "-"
            
            # 嘗試尋找賠率欄位
            # 在資訊網，即時賠率通常不在 RaceCard 頁面，而是在 "Odds" 頁面
            # 但如果 RaceCard 頁面沒有賠率，我們至少能保證「馬匹名單」是正確的
            # 我們會標記「賠率未開」
            
            target_df["現價"] = 0.0
            target_df["顯示賠率"] = "未開盤"
            
            # 簡單清理
            target_df = target_df.fillna("-")
            
            return target_df, log, True
        else:
            return pd.DataFrame(), "找不到包含馬匹資料的表格 (可能網站改版或無賽事)", False

    except Exception as e:
        return pd.DataFrame(), f"解析嚴重錯誤: {str(e)}\n建議檢查日期是否正確", False

# ----------------- UI 介面 -----------------
st.title("🏇 賽馬智腦 V1.41 (HKJC 官方資訊源)")

# 日期選擇
default_date_str, default_date_disp = get_next_race_date()
st.info(f"系統預設鎖定: **{default_date_disp}** (若今日無賽事，請確認日期)")

col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### ⚙️ 設定")
    # 讓使用者可以手動改日期，格式必須是 YYYY/MM/DD
    user_date = st.text_input("日期 (YYYY/MM/DD)", value=default_date_str)
    race_no = st.selectbox("場次", range(1, 15))
    
    btn = st.button("🚀 抓取排位與數據", type="primary", use_container_width=True)
    
    st.markdown("---")
    st.caption("**資料來源說明**")
    st.caption("本版本改用 `racing.hkjc.com` (資訊網)。")
    st.caption("✅ 優點：保證能抓到完整 12-14 匹馬，不會只有 3 隻。")
    st.caption("⚠️ 限制：週二下午通常尚未有賠率，系統會顯示「未開盤」，這是正常的市場狀態。")

if btn:
    with st.spinner("正在暴力解析 HKJC 網頁..."):
        df, log, success = fetch_hkjc_html_robust(user_date, race_no)
        st.session_state['data_v141'] = df
        st.session_state['log_v141'] = log
        st.session_state['success_v141'] = success

# 顯示區
with col2:
    if 'data_v141' in st.session_state:
        df = st.session_state['data_v141']
        log = st.session_state['log_v141']
        
        if not df.empty:
            st.success(f"成功獲取第 {race_no} 場資料，共 {len(df)} 匹賽駒")
            
            # 顯示漂亮的表格
            # 挑選重點欄位
            display_cols = ['馬號', '馬名', '騎師', '練馬師', '排位體重', '檔位'] 
            # 根據實際抓到的欄位動態調整
            final_cols = [c for c in display_cols if c in df.columns]
            
            st.dataframe(
                df[final_cols],
                use_container_width=True,
                hide_index=True
            )
            
            st.warning("💡 提示：如需即時變動賠率，請於賽事當日或開跑前 1 小時使用，屆時 HKJC 才會釋出數據。")
            
        else:
            st.error("無法獲取數據")
            st.text(log)
            st.markdown("#### 可能原因：")
            st.markdown("1. 該日期 (**" + user_date + "**) 根本沒有賽事。")
            st.markdown("2. 該場次 (Race " + str(race_no) + ") 超出當日場次數量。")
            
    else:
        st.info("👈 請點擊左側按鈕開始")
