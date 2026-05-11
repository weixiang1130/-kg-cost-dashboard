# 成本管理自動化監測系統 v8

## 地端執行說明

本系統完全在本機運行，不需要部署到網路伺服器。

Streamlit 啟動時會自動在本機建立一個 Web 伺服器，透過 http://localhost:8501 提供服務。
localhost 只有你的電腦能存取，外部網路無法連入，資料完全私有。

## 需要的檔案（同一資料夾）

- kg_dashboard.py            主程式
- kg_cost_analysis_v14.py    造價分析引擎
- start_dashboard.bat        Windows 快速啟動

執行後自動產生:
- kg_history.db              SQLite 歷史資料庫
- kg_areas.json              各專案面積設定
- kg_data/                   上傳的 KG 一覽表

## 啟動方式

雙擊 start_dashboard.bat，或命令列執行:
  streamlit run kg_dashboard.py

瀏覽器會自動開啟 http://localhost:8501
要停止系統在命令列視窗按 Ctrl+C

## 三個功能

1. 假設工程分析：13 項假設工程結算追蹤 + 趨勢
2. 自動造價分析：產出造價 Excel + 八大類分析  
3. 歷史記錄：查看/下載過往所有分析

## SQLite 資料庫

kg_history.db 包含兩個表，儲存所有分析歷史。
造價分析的 Excel 完整存在資料庫裡，日後可隨時重新下載。

系統偵測到相同專案名時，會自動提示已有歷史，執行後顯示與上次的增減。

## 資料備份

複製 kg_history.db 和 kg_areas.json 到新電腦即可。
