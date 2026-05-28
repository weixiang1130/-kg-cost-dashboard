// 總覽儀表板
const { useState: useStateH, useEffect: useEffectH, useRef: useRefH } = React;

function PageHome({ setPage }) {
  const [projects, setProjects] = useStateH(null);
  const [typeCounts, setTypeCounts] = useStateH(null);
  const [loading, setLoading] = useStateH(true);
  const [error, setError] = useStateH(null);
  const [dragOver, setDragOver] = useStateH(false);
  const fileRef = useRefH(null);

  useEffectH(() => {
    Promise.all([API.getProjects(), API.getTypeCounts()])
      .then(([p, tc]) => { setProjects(p); setTypeCounts(tc); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function handleDrop(files) {
    window.__batchFiles = files;
    setPage('batch');
  }

  if (loading) return <div className="empty"><h4>載入中...</h4><p>正在連線後端 API</p></div>;
  if (error) return (
    <div className="empty">
      <h4>連線錯誤</h4><p>{error}</p>
      <p className="muted" style={{fontSize:12}}>請確認 FastAPI 後端已啟動（start_api.bat）</p>
    </div>
  );

  const ac = typeCounts?.assumption || {};
  const cc = typeCounts?.cost || {};
  const totalA = projects?.total_assumption_names || 0;
  const totalC = projects?.total_cost_names || 0;

  return (
    <>
      <TopBar title="總覽儀表板"
        subtitle="跨專案成本即時監測．假設工程 + 造價分析快照總覽"
        actions={<Btn kind="primary" icon={ICONS.upload} onClick={() => setPage('batch')}>批次匯入 Excel</Btn>}
      />

      {/* Drop zone on homepage */}
      <div className={'batch-drop-zone batch-drop-compact' + (dragOver ? ' batch-drop-active' : '')}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault(); setDragOver(false);
          const files = Array.from(e.dataTransfer.files).filter(f => /\.xlsx?$/i.test(f.name));
          if (files.length > 0) handleDrop(files);
        }}
        onClick={() => fileRef.current?.click()}>
        <span className="batch-drop-icon-sm" style={{width:22, height:22, flexShrink:0, display:'inline-flex'}} dangerouslySetInnerHTML={{__html: ICONS.upload}}/>
        <span style={{fontWeight:600, fontSize:13}}>拖放 Excel 檔案至此批次匯入</span>
        <span className="muted" style={{fontSize:12}}>或點擊選取 · 自動偵測假設工程 / 造價分析並帶入面積</span>
        <input ref={fileRef} type="file" accept=".xlsx,.xls" multiple
          style={{display:'none'}}
          onChange={e => {
            if (e.target.files.length > 0) handleDrop(Array.from(e.target.files));
          }}/>
      </div>

      <div className="grid grid-4">
        <KPI label="假設工程專案" value={totalA} sub="DB 中的專案數" color="var(--primary-500)"/>
        <KPI label="造價分析專案" value={totalC} sub="DB 中的專案數" color="var(--primary-500)"/>
        <KPI label="FAB 類案件" value={(ac.FAB||0)+(cc.FAB||0)} sub="假設+造價合計" color="var(--good)" tone="good"/>
        <KPI label="CUP 類案件" value={(ac.CUP||0)+(cc.CUP||0)} sub="假設+造價合計" color="var(--accent)"/>
      </div>

      <div className="grid grid-2" style={{marginTop:16}}>
        <Card title="假設工程 — 類型分佈" accent="var(--primary-500)">
          {Object.keys(ac).length > 0 ? (
            <div className="stack">
              {Object.entries(ac).map(([t,c]) => (
                <div key={t} className="row-between" style={{padding:'6px 0'}}>
                  <Pill tone="muted">{t}</Pill>
                  <span className="num" style={{fontWeight:600}}>{c} 筆</span>
                </div>
              ))}
            </div>
          ) : <EmptyState title="尚無資料" sub="匯入 KG 一覽表以新增快照"/>}
        </Card>
        <Card title="造價分析 — 類型分佈" accent="var(--accent)">
          {Object.keys(cc).length > 0 ? (
            <div className="stack">
              {Object.entries(cc).map(([t,c]) => (
                <div key={t} className="row-between" style={{padding:'6px 0'}}>
                  <Pill tone="muted">{t}</Pill>
                  <span className="num" style={{fontWeight:600}}>{c} 筆</span>
                </div>
              ))}
            </div>
          ) : <EmptyState title="尚無資料" sub="上傳造價 Excel"/>}
        </Card>
      </div>

      <h3 className="section-label">快速動作</h3>
      <div className="grid grid-4">
        <QuickAction icon={ICONS.upload} title="批次匯入" sub="多檔上傳、自動偵測分析" onClick={() => setPage('batch')}/>
        <QuickAction icon={ICONS.cost} title="造價分析" sub="單檔上傳、八大類下鑽" onClick={() => setPage('cost')}/>
        <QuickAction icon={ICONS.prediction} title="開立投標預估" sub="依面積回歸預估造價" onClick={() => setPage('prediction')}/>
        <QuickAction icon={ICONS.history} title="檢視歷史記錄" sub="所有快照時間線" onClick={() => setPage('history')}/>
      </div>
    </>
  );
}

function QuickAction({ icon, title, sub, onClick }) {
  return (
    <button className="quick-action" onClick={onClick}>
      <span className="qa-icon" dangerouslySetInnerHTML={{__html: icon}}/>
      <span style={{flex:1, textAlign:'left'}}>
        <div style={{fontWeight:600, fontSize:13}}>{title}</div>
        <div className="muted" style={{fontSize:11.5, marginTop:2}}>{sub}</div>
      </span>
      <span className="qa-arrow" dangerouslySetInnerHTML={{__html: ICONS.arrowRight}}/>
    </button>
  );
}

Object.assign(window, { PageHome });
