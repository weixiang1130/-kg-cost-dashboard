# CHANGELOG - 成本管理自動化監測系統

所有重要變更皆記錄於此檔案。格式依循 [Keep a Changelog](https://keepachangelog.com/)。

---

## [v2.0.0] - 2026-05-21

### Changed
- **UI/UX 全面改版（Hallmark · modern-minimal · utilitarian-technical）**
  - OKLCH-ready 語義化色彩 token 系統（--color-paper / surface / ink / primary / accent / good / bad）
  - 4pt 間距系統（--space-xs 到 --space-2xl）
  - 側邊欄：Logo mark + 公司名稱 + 無圓點導航 + 版本資訊
  - 頁面標題：麵包屑 + 24px 大標題 + 13px 副標
  - KPI 卡片：3px 左色條 + uppercase 標籤 + 26px mono 數值 + hover 浮起
  - 按鈕：ghost 預設（白底 + 邊框）+ gradient primary
  - 分頁標籤：pill 膠囊式（surface-2 底 + 白色啟用態）
  - 表格：surface-2 表頭 + uppercase 11.5px 欄名 + hover 列
  - 首頁新增 KPI 統計列（專案數 / 快照數 / 假設工程 / 造價分析）
  - h2 標題加入 4px 藍色左 accent bar
  - 全域自訂 scrollbar（6px 窄軌）
  - SVG icon 統一 stroke-width 1.8
  - 移除舊版 gradient-text h1、logo-bar、amber 底線 h2

---

## [v1.4.1] - 2026-05-11

### Changed
- **發包條件表單排版優化**：將條件輸入從狹窄的專案欄位移至全寬區域
  - 拆分為 `render_conditions_input()`（資料初始化）與 `render_conditions_section()`（UI 渲染）
  - 多專案以分頁（Tabs）切換，單專案直接顯示
  - 三區塊分組（工程特徵/發包條件/市場行情）+ 區塊間距
  - 欄位改為 3 欄 + 2 欄配置，畫面更寬敞不擁擠
  - 使用可收合 Expander，預設收合，減少視覺負擔

---

## [v1.4.0] - 2026-05-11

### Added
- **發包條件標註系統**：每筆快照可記錄完整的發包條件與市場行情
  - 工程特徵：廠區代號（自動偵測）、地區（自動偵測）、結構型式、樓層數、工期
  - 發包條件：發包方式（點工/包工/連工帶料）、是否帶料、是否帶機具
  - 市場行情：鋼筋單價、混凝土單價、模板單價、營造物價指數
  - 備註欄位：記錄特殊條件、趕工情形等
- 自動偵測函數：`detect_fab_code()`（從專案名擷取廠區代號）、`detect_region()`（猜測地區）
- DB 新增 `conditions_json` 欄位（兩張表皆有）
- 假設工程分析 & 造價分析頁面新增可展開的條件輸入表單
- 投標預估頁「歷史同類專案」表格新增廠區、地區、結構、發包方式等條件欄位

### Purpose
為未來第二階段多變數回歸與機器學習預測奠定資料基礎。條件記錄越完整，未來預估越準確。

---

## [v1.3.0] - 2026-05-11

### Added
- **R² 決定係數說明面板**：投標預估頁新增可展開的公式說明與判讀建議表格（極好/良好/普通/不佳四級），供長官投標時參考
- **歷史資料管理面板**：投標預估頁新增「管理歷史資料」，可勾選排除或永久刪除不需要的快照（無面積資料預設排除）
- **版本控制**：專案納入 Git 管理，新增 CHANGELOG.md 記錄更新歷程

### Fixed
- 修復 `page_cost_analysis` 同專案多期檔案導致 `StreamlitDuplicateElementKey` 錯誤（面積輸入依 dn 去重）
- 修復 `_tab_assumption_trend` 多專案趨勢圖 `plotly_chart` 重複 ID 錯誤（加入唯一 key）
- 修復 Windows CP950 編碼錯誤：移除所有 Unicode 特殊符號（⚠ U+26A0），改用 ASCII 替代

---

## [v1.2.0] - 2026-05-11

### Added
- **UI/UX 全面升級**：套用 Data-Dense Dashboard 設計風格
  - 深藍漸層 Logo 橫條（白色文字）
  - 漸層文字標題（h1）+ 琥珀色底線（h2）
  - 首頁導覽卡片：SVG 圖示 + 彩色圖示容器（藍/琥珀/綠/紫）+ 懸停動畫
  - 左側色條 Metric 卡片 + 懸停浮起效果
  - 漸層主要按鈕 + 幽靈次要按鈕
  - 藥丸式分頁標籤 + 琥珀色啟用指示器
  - 漸層表格標題 + 精緻陰影系統
  - Google Fonts 引入（Fira Code + Noto Sans TC）

---

## [v1.1.0] - 2026-05-07

### Added
- **投標預估功能**：依專案類型 + 樓地板面積，回歸預估工程造價
  - 專案分類：FAB / CUP / OFFICE / 物流中心 / 其他
  - 自動偵測專案類型（`detect_project_type`，從檔名/專案名猜測）
  - 線性回歸引擎（`numpy.polyfit`）+ R² 決定係數
  - 95% 信賴區間（`scipy.stats`）
  - 預估結果：總造價、元/坪、R²、資料量
  - 散佈圖 + 回歸線 + 預估點視覺化
  - 八大類預估分佈（圓餅圖 + 表格）
  - 13 項假設工程預估明細
  - 歷史同類專案一覽
- DB 新增 `project_type` 欄位（assumption_snapshots / cost_snapshots）
- 假設工程分析 & 造價分析頁面新增專案類型選擇器

---

## [v1.0.0] - 2026-05-01

### Added
- **假設工程分析**：上傳 KG 一覽表 → 自動解析 13 項假設工程 → 即時預覽 → 儲存快照
- **造價分析**：八大類工程造價統計 → 產出 Excel
- **歷史記錄**：查看過往快照、下載 Excel、趨勢圖
- **面積管理**：坪/m² 自動換算、跨頁共用
- **SQLite 快照資料庫**：自動初始化、多專案多期儲存
- **KG 一覽表解析引擎**：openpyxl + XML 解析、自動識別專案名/日期
