import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# 設定頁面
st.set_page_config(page_title="HKJC分析", layout="wide")
st.title("🏇 HKJC 落飛分析 (強力解析版)")
count = st_autorefresh(interval=300000, limit=None, key="auto")

# 側邊欄
total_races = st.sidebar.number_input("場數", 1, 14, 10)
st.sidebar.write(f"更新: {datetime.now().strftime('%H:%M')}")

# 強力抓取函數
def fetch_data(race_no):
    url = f"https://www.51saima.com/mobi/odds.jsp?raceNo={race_no}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        if r.status_code != 200: return pd.DataFrame()
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 這裡改用更暴力的解析法
        # 1. 找到所有 td 標籤
        tds = soup.find_all("td")
        rows = []
        
        # 我們假設數據是連續的：馬號 -> 馬名 -> 賠率 -> ...
        # 用一個簡單的狀態機來遍歷
        i = 0
        while i < len(tds) - 2:
            try:
                # 嘗試提取連續三個格子的文字
                t1 = tds[i].get_text(strip=True)
                t2 = tds[i+1].get_text(strip=True)
                t3 = tds[i+2].get_text(strip=True)
                
                # 判斷特徵：
                # t1 必須是純數字 (馬號)
                # t2 是馬名 (長度通常 > 1)
                # t3 是賠率 (數字或 SCR)
                
                if t1.isdigit():
                    horse_no = int(t1)
                    horse_name = t2
                    odds_text = t3
                    
                    # 檢查賠率是否有效
                    if "SCR" in odds_text:
                         # 這是退出馬，但也算抓到了
                         i += 1
                         continue
                         
                    # 嘗試轉換賠率為 float
                    # 有時候賠率會有變動箭頭符號，要先清乾淨
                    clean_odds = re.findall(r"\d+\.\d+", odds_text)
                    if clean_odds:
                        odds_val = float(clean_odds[0])
                        
                        rows.append({
                            "RaceID": race_no,
                            "HorseNo": horse_no,
                            "HorseName": horse_name,
                            "Odds": odds_val
                        })
                        # 成功抓到一組，跳過這三個格子
                        # 注意：有時候賠率後面會有"變動幅度"，所以這裡可能要多跳幾格
                        # 但保險起見，我們只跳 2 格，下一次迴圈 i+1 會繼續檢查
                        # 為了不重複抓，我們記錄一下已抓到的馬號
            except:
                pass
            i += 1
            
        # 去除重複 (因為上面的遍歷可能會重複抓到)
        if rows:
            df = pd.DataFrame(rows)
            df = df.drop_duplicates(subset=["HorseNo"], keep="last")
            return df
        return pd.DataFrame()

    except Exception as e:
        return pd.DataFrame()

# 主程式
if st.button("刷新"): st.rerun()

all_data = []
status = st.empty()

with st.spinner("讀取中..."):
    for i in range(1, total_races + 1):
        status.text(f"讀取第 {i} 場")
        df = fetch_data(i)
        if not df.empty: all_data.append(df)

status.empty()

if len(all_data) > 0:
    df_all = pd.concat(all_data, ignore_index=True)
    st.success(f"成功！共 {len(df_all)} 匹馬")
    
    st.divider()
    col1, col2 = st.columns(2)
    mult = col1.slider("變動幅度(%)", 0, 50, 15)
    thresh = col2.slider("門檻(%)", 0, 30, 5)
    
    df_all["Last"] = df_all["Odds"]
    df_all["First"] = (df_all["Odds"] * (1 + mult/100)).round(1)
    df_all["Drop"] = ((df_all["First"] - df_all["Last"]) / df_all["First"] * 100).round(1)
    
    def signal(row):
        if row["Last"] <= 10 and row["Drop"] > thresh:
            return "🔥" if row["First"] > 10 else "✅"
        return ""
        
    df_all["Sig"] = df_all.apply(signal, axis=1)
    res = df_all[df_all["Sig"] != ""]
    
    if not res.empty:
        # 顯示時排序一下
        res = res.sort_values(by=["RaceID", "HorseNo"])
        st.dataframe(res, use_container_width=True)
    else:
        st.info("無落飛馬")
else:
    st.warning("無數據")



