// Shared UI components
const { useState: useStateUI, useEffect: useEffectUI } = React;

function Logo() {
  return (
    <div className="logo">
      <div className="logo-mark">
        <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
          <rect x="3" y="3" width="26" height="26" rx="4" fill="#2A4357"/>
          <rect x="3" y="3" width="26" height="3.5" fill="#EA580C"/>
          <path d="M10 23 L10 11 L22 23 L22 11" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        </svg>
      </div>
      <div className="logo-text">
        <div className="logo-name">根基營造</div>
        <div className="logo-sub">KEDGE · 成本監測</div>
      </div>
    </div>
  );
}

function NavItem({ icon, label, badge, active, onClick }) {
  return (
    <button className={'nav-item' + (active ? ' active' : '')} onClick={onClick}>
      <span className="nav-icon" dangerouslySetInnerHTML={{__html: icon}}/>
      <span className="nav-label">{label}</span>
      {badge != null && <span className="nav-badge">{badge}</span>}
    </button>
  );
}

function Sidebar({ page, setPage }) {
  const items = [
    { key:'home',       label:'總覽儀表板', icon: ICONS.home },
    { key:'batch',      label:'批次匯入', icon: ICONS.upload },
    { key:'assumption', label:'假設工程分析', icon: ICONS.assumption },
    { key:'cost',       label:'造價分析', icon: ICONS.cost },
    { key:'prediction', label:'投標預估', icon: ICONS.prediction },
    { key:'history',    label:'歷史記錄', icon: ICONS.history },
  ];
  return (
    <aside className="sidebar">
      <Logo/>
      <button className="upload-cta" onClick={() => setPage('batch')}>
        <span className="nav-icon" dangerouslySetInnerHTML={{__html: ICONS.upload}}/>
        <span style={{whiteSpace:'nowrap'}}>批次匯入 Excel</span>
      </button>
      <nav className="nav">
        <div className="nav-section">主功能</div>
        {items.map(it => (
          <NavItem key={it.key} {...it} active={page === it.key} onClick={() => setPage(it.key)}/>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div className="version">v2.2.0 · 2026.06</div>
      </div>
    </aside>
  );
}

function TopBar({ title, subtitle, actions, breadcrumb }) {
  return (
    <header className="topbar">
      <div>
        {breadcrumb && <div className="crumb">{breadcrumb}</div>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <div className="page-sub">{subtitle}</div>}
      </div>
      <div className="topbar-actions">{actions}</div>
    </header>
  );
}

function Card({ title, action, children, className = '', accent }) {
  return (
    <section className={'card ' + className}>
      {(title || action) && (
        <header className="card-head">
          <div>
            {accent && <span className="card-accent" style={{background: accent}}/>}
            <h3>{title}</h3>
          </div>
          {action}
        </header>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}

function KPI({ label, value, sub, delta, deltaPositive, spark, color, tone = 'default' }) {
  const positive = deltaPositive ?? (delta && !String(delta).trim().startsWith('-'));
  return (
    <div className={'kpi tone-' + tone}>
      <div className="kpi-head">
        <span className="kpi-label">{label}</span>
        {delta && (
          <span className={'kpi-delta ' + (positive ? 'up' : 'down')}>
            <span dangerouslySetInnerHTML={{__html: positive ? ICONS.arrowUp : ICONS.arrowDown}}/>
            {delta}
          </span>
        )}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        <span className="kpi-sub">{sub}</span>
        {spark && <Sparkline values={spark} color={color || 'var(--primary-500)'} w={88} h={28}/>}
      </div>
    </div>
  );
}

function Pill({ children, tone = 'default', style }) {
  return <span className={'pill pill-' + tone} style={style}>{children}</span>;
}

function Btn({ children, kind = 'ghost', icon, onClick, disabled, size }) {
  return (
    <button className={`btn btn-${kind}` + (size ? ` btn-${size}` : '')} onClick={onClick} disabled={disabled}>
      {icon && <span className="btn-icon" dangerouslySetInnerHTML={{__html: icon}}/>}
      {children}
    </button>
  );
}

function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  useEffectUI(() => {
    if (!open) return;
    const onKey = e => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal-scrim" onClick={onClose}>
      <div className={'modal modal-' + size} onClick={e => e.stopPropagation()}>
        <header className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} dangerouslySetInnerHTML={{__html: ICONS.close}}/>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

function ProgressBar({ value, max = 1, color = 'var(--primary-500)', height = 6, showLabel }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="pbar-wrap">
      <div className="pbar" style={{height}}>
        <div className="pbar-fill" style={{width: pct + '%', background: color}}/>
      </div>
      {showLabel && <span className="pbar-label">{pct.toFixed(0)}%</span>}
    </div>
  );
}

function Tabs({ tabs, active, onChange }) {
  return (
    <div className="tabs">
      {tabs.map(t => (
        <button key={t.key} className={'tab' + (active === t.key ? ' active' : '')} onClick={() => onChange(t.key)}>
          {t.label}
          {t.count != null && <span className="tab-count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

function EmptyState({ title, sub, icon, action }) {
  return (
    <div className="empty">
      <div className="empty-icon" dangerouslySetInnerHTML={{__html: icon || ICONS.upload}}/>
      <h4>{title}</h4>
      <p>{sub}</p>
      {action}
    </div>
  );
}

Object.assign(window, { Logo, NavItem, Sidebar, TopBar, Card, KPI, Pill, Btn, Modal, ProgressBar, Tabs, EmptyState });
