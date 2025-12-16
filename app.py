import streamlit as st
import pandas as pd
import re
import requests
import time
import random
import os
import json
from datetime import datetime, timedelta, timezone

# ----------------- 設定區 -----------------
APP_VERSION = "V1.38 (Fix)"
HISTORY_FILE = "race_history.json"
HKT = timezone(timedelta(hours=8))
HEADERS = {"User-Agent": "Mozilla/5.0"}

# ----------------- 快取與資料 -----------------
@st.cache_resource
def get_storage():
    data = {}
    for i in range(1, 15):
        data[i] = {"current_df": pd.DataFrame(), "last_update": "無數據", "debug_info": ""}
    return data

race_storage = get_storage()

JOCKEY_DB = ['Purton', 'McDonald', 'Bowman', 'Teetan', 'Ho', 'Ferraris', 'Bentley']
TRAINER_DB = ['Size', 'Lui', 'Ng', 'Lor', 'Shum', 'Yiu', 'Cruz', 'Fownes']

def get_score(row):
    """計算馬匹得分"""
    s = 0
    price = row.get("現價", 0)
    
    # 賠率分數
    if price > 0 and price <= 5.0:
        s += 25
    elif price > 5.0 and price <= 10.0:
        s += 10
        
    # 走勢分數
    trend = row.get("走勢", 0)
    if trend >= 15:
        s += 50
    elif trend >= 10:
        s += 35
    elif trend >= 5:
        s += 20
        
    return round(s, 1)

def fetch_data_simple(r_no):
    """簡化版數據抓取 (僅抓取 HKJC JSON)"""
    log = f"正在抓取第 {r_no} 場...\n"
    data_list = []
    
    try:
        url = "https://bet.hkjc.com/racing/jsonData.aspx"
        # 參數設置
        params = {
            "type": "winodds", 
            "date": datetime.now(HKT).strftime("%Y-%m-%d"), 
            "venue": "HV", 
            "start": r_no, 
            "end": r_no
        }
        
        resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
        
        if resp.status_code == 200:
            # 嘗試解析 JSON 格式的回傳
            # 格式通常是: "1"="2.5";"2"="10.0";...
            matches = re.findall(r'(\d+)\s*=\s*(\d+\.\d+)', resp.text)
            
            # 如果找不到，嘗試另一種格式 "1":"2.5"
            if not matches:
                matches = re.findall(r'"(\d+)"\s*:\s*"(\d+\.\d+)"', resp.text)
            
            for m in matches:
                horse_no = int(m[0])
                odds = float(m[1])
                data_list.append({
                    "馬號": horse_no,
                    "馬名": f"馬匹 {horse_no}", # 暫時用假名，確保不報錯
                    "現價": odds,
                    "騎師": "-",
                    "練馬師": "-"
                })
            
            log += f"成功獲取 {len(data_list)} 筆賠率數據"
        else:
            log += f"HTTP 錯誤: {resp.status_code}"
            
    except Exception as e:
        log += f"錯誤: {str(e)}"
        
    return pd.DataFrame(data_list), log

# ----------------- UI 介面 -----------------
st.set_page_config(page_title="賽馬智腦Lite", layout="wide")

st.title(f"🐎 賽馬智腦 {APP_VERSION}")

col1, col2 = st.columns([1, 3])

with col1:
    st.markdown("### 控制台")
    sel_race = st.number_input("選擇場次", min_value=1, max_value=14, value=1)
    
    if st.button("🔄 更新數據", type="primary", use_container_width=True):
        df_new, log = fetch_data_simple(sel_race)
        
        # 儲存數據
        curr = race_storage[sel_race]
        curr["debug_info"] = log
        
        if not df_new.empty:
            # 計算走勢
            if not curr["current_df"].empty:
                last_df = curr["current_df"][["馬號", "現價"]].rename(columns={"現價": "上回"})
                df_new = df_new.merge(last_df, on="馬號", how="left")
                df_new["上回"] = df_new["上回"].fillna(df_new["現價"])
                df_new["走勢"] = ((df_new["上回"] - df_new["現價"]) / df_new["上回"] * 100).round(1)
            else:
                df_new["走勢"] = 0.0
                
            curr["current_df"] = df_new
            curr["last_update"] = datetime.now(HKT).strftime("%H:%M:%S")
            st.success("更新成功")
            st.rerun()
        else:
            st.error("更新失敗")

# 顯示區域
curr_data = race_storage[sel_race]

with col2:
    st.info(f"第 {sel_race} 場 | 更新時間: {curr_data['last_update']}")
    
    with st.expander("查看日誌"):
        st.text(curr_data["debug_info"])
        
    if not curr_data["current_df"].empty:
        df_display = curr_data["current_df"].copy()
        df_display["得分"] = df_display.apply(get_score, axis=1)
        
        # 排序
        df_display = df_display.sort_values("得分", ascending=False).reset_index(drop=True)
        
        # 顯示卡片
        best_horse = df_display.iloc[0]
        st.metric("推薦首選", f"#{best_horse['馬號']} (得分: {best_horse['得分']})", f"賠率: {best_horse['現價']}")
        
        st.dataframe(
            df_display,
            column_config={
                "現價": st.column_config.NumberColumn("賠率", format="%.1f"),
                "走勢": st.column_config.NumberColumn("走勢 (%)", format="%.1f%%"),
            },
            use_container_width=True
        )
    else:
        st.warning("暫無數據，請點擊左側「更新數據」")
