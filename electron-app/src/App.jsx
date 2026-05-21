/**
 * App 殼 — 路由 + Sidebar 導航
 * Phase 2 會填入完整頁面元件，目前是 placeholder
 */
import React, { useState } from 'react';

// 頁面佔位（Phase 2 填入）
const PageHome       = () => <div className="page-placeholder">總覽儀表板 — Phase 2 實作</div>;
const PageAssumption = () => <div className="page-placeholder">假設工程分析 — Phase 2 實作</div>;
const PageCost       = () => <div className="page-placeholder">造價分析 — Phase 2 實作</div>;
const PagePrediction = () => <div className="page-placeholder">投標預估 — Phase 2 實作</div>;
const PageHistory    = () => <div className="page-placeholder">歷史記錄 — Phase 2 實作</div>;

const NAV = [
  { key: 'home',       label: '總覽儀表板',   icon: '◆' },
  { key: 'assumption', label: '假設工程分析', icon: '▤' },
  { key: 'cost',       label: '造價分析',     icon: '▥' },
  { key: 'prediction', label: '投標預估',     icon: '◎' },
  { key: 'history',    label: '歷史記錄',     icon: '↻' },
];

const PAGES = {
  home: PageHome,
  assumption: PageAssumption,
  cost: PageCost,
  prediction: PagePrediction,
  history: PageHistory,
};

export default function App() {
  const [page, setPage] = useState('home');
  const Page = PAGES[page] || PageHome;

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">N</div>
          <div>
            <div className="sidebar-logo-text">根基營造</div>
            <div className="sidebar-logo-sub">KEDGE · 成本監測</div>
          </div>
        </div>
        <div className="sidebar-section">主功能</div>
        <nav className="sidebar-nav">
          {NAV.map(n => (
            <button
              key={n.key}
              className={`sidebar-item ${page === n.key ? 'active' : ''}`}
              onClick={() => setPage(n.key)}
            >
              <span className="sidebar-item-icon">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="sidebar-version">v2.1.0 · 2026.05</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        <Page setPage={setPage} />
      </main>
    </div>
  );
}
