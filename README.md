# 成本管理自動化監測系統

> **Current Version: v2.1.0** | Last Updated: 2026-05-21

---

## 地端執行說明

本系統完全在本機運行，不需要部署到網路伺服器。
localhost 只有你的電腦能存取，外部網路無法連入，資料完全私有。

## 專案結構

```
kg_dashboard.py            Streamlit 儀表板（UI 層）
kg_cost_analysis_v14.py    造價分析引擎
core/                      業務邏輯模組
  constants.py               共用常數
  conditions.py              專案條件偵測
  parser.py                  KG 一覽表 XML 解析
  db.py                      SQLite 資料庫操作
  areas.py                   面積設定管理
  analysis.py                回歸分析與預估
  utils.py                   通用工具函式
api_server.py              FastAPI REST API（供未來 Electron 前端使用）
start_dashboard.bat        Windows 快速啟動 Streamlit
start_api.bat              Windows 快速啟動 API Server
test_api.py                API 端點驗證腳本
requirements.txt           Python 依賴清單
```

執行後自動產生:
- kg_history.db              SQLite 歷史資料庫
- kg_areas.json              各專案面積設定
- kg_data/                   上傳的 KG 一覽表

## 安裝依賴

  pip install -r requirements.txt

## 啟動方式

### Streamlit 儀表板（現行）
雙擊 start_dashboard.bat，或：
  streamlit run kg_dashboard.py
瀏覽器會自動開啟 http://localhost:8501

### FastAPI 後端（Phase 2 準備）
雙擊 start_api.bat，或：
  uvicorn api_server:app --reload --port 8000
API 文件：http://localhost:8000/docs

要停止系統在命令列視窗按 Ctrl+C

## 功能總覽

1. **假設工程分析**：13 項假設工程結算追蹤 + 跨期趨勢比對
2. **造價分析**：八大類工程造價統計 + 產出 Excel
3. **投標預估**：依專案類型 + 面積回歸預估造價（含 R² 信心指標）
4. **歷史記錄**：查看/下載過往所有分析快照

## SQLite 資料庫

kg_history.db 包含兩個表，儲存所有分析歷史。
造價分析的 Excel 完整存在資料庫裡，日後可隨時重新下載。

系統偵測到相同專案名時，會自動提示已有歷史，執行後顯示與上次的增減。

## 資料備份

複製 kg_history.db 和 kg_areas.json 到新電腦即可。

---

## 更新記錄

### v2.0.0 - 2026-05-21
- UI/UX 全面改版（Hallmark design）：語義化 token 系統、pill 分頁、KPI 統計列、scrollbar、accent bar 標題

### v1.4.1 - 2026-05-11
- 優化發包條件表單排版：全寬區域 + 分頁切換 + 三區塊分組，畫面更寬敞

### v1.4.0 - 2026-05-11
- 新增「發包條件標註系統」：每筆快照可記錄廠區代號、地區、結構型式、樓層數、工期、發包方式、帶料/帶機具、鋼筋/混凝土/模板單價、營造物價指數、備註
- 自動偵測廠區代號（AP7P1、F22P5 等）與地區（竹科/中科/南科）
- 投標預估頁歷史同類專案表格新增條件欄位，方便比較

### v1.3.0 - 2026-05-11
- 新增 R² 決定係數說明面板（公式 + 四級判讀建議）
- 新增歷史資料管理面板（排除/刪除快照）
- 修復同專案多期檔案的重複 Key 錯誤
- 修復 Windows CP950 編碼錯誤
- 專案納入 Git 版本控制

### v1.2.0 - 2026-05-11
- UI/UX 全面升級：深藍漸層 Logo、SVG 圖示導覽卡片、琥珀色點綴、精緻陰影與動畫

### v1.1.0 - 2026-05-07
- 新增「投標預估」功能：專案分類（FAB/CUP/OFFICE/物流中心）、線性回歸預估、95% 信賴區間、八大類分佈預估、13 項假設工程明細

### v1.0.0 - 2026-05-01
- 初始版本：假設工程分析、造價分析、歷史記錄、面積管理、SQLite 快照資料庫
