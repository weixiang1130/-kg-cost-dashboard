// 歷史記錄 — 跨專案快照清單 + 管理 + 備份 + 資料品質
const { useState: useStateHi, useEffect: useEffectHi } = React;

function PageHistory({ setPage }) {
  const [table, setTable] = useStateHi('assumption_snapshots');
  const [snapshots, setSnapshots] = useStateHi([]);
  const [loading, setLoading] = useStateHi(true);
  const [health, setHealth] = useStateHi(null);
  const [backing, setBacking] = useStateHi(false);
  const [backupMsg, setBackupMsg] = useStateHi(null);

  async function loadHistory(t) {
    setLoading(true);
    try {
      const data = await API.getHistory(t);
      const snapsObj = data?.snapshots || {};
      const flat = Object.values(snapsObj).flat();
      setSnapshots(flat);
    } catch {
      setSnapshots([]);
    } finally {
      setLoading(false);
    }
  }

  async function loadHealth() {
    try {
      const data = await API.getHealth();
      setHealth(data);
    } catch { setHealth(null); }
  }

  useEffectHi(() => { loadHistory(table); loadHealth(); }, [table]);

  async function handleDelete(sid) {
    if (!confirm('確定刪除此快照？此操作不可復原。')) return;
    try {
      await API.deleteSnapshot(table, sid);
      loadHistory(table);
      loadHealth();
    } catch (e) {
      alert('刪除失敗：' + e.message);
    }
  }

  async function handleDownload(sid) {
    try {
      const result = await API.downloadExcel(sid);
      if (result?.blob) {
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = result.filename || 'export.xlsx';
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      alert('下載失敗：' + e.message);
    }
  }

  async function handleBackup() {
    setBacking(true);
    setBackupMsg(null);
    try {
      const result = await API.createBackup();
      setBackupMsg({
        ok: true,
        text: '備份成功：' + result.filename + '（' + Math.round(result.size / 1024) + ' KB）'
      });
      loadHealth();
    } catch (e) {
      setBackupMsg({ ok: false, text: '備份失敗：' + e.message });
    } finally {
      setBacking(false);
    }
  }

  const isAssumption = table === 'assumption_snapshots';

  // Health score color
  function scoreColor(score) {
    if (score >= 90) return 'var(--good)';
    if (score >= 70) return 'var(--warn)';
    return 'var(--bad)';
  }

  return (
    <>
      <TopBar
        title="歷史記錄"
        breadcrumb="總覽 / 歷史記錄"
        subtitle={`共 ${snapshots.length} 筆歷史快照`}
      />

      {/* ── Health & Backup panel ── */}
      {health && (
        <div className="grid grid-4" style={{marginBottom:16}}>
          <KPI label="資料健康度"
            value={health.score + '%'}
            sub={health.score >= 90 ? '狀態良好' : health.score >= 70 ? '有待改善' : '需要注意'}
            color={scoreColor(health.score)}/>
          <KPI label="假設工程"
            value={health.assumption?.total || 0}
            sub={
              (health.assumption?.zero_settle > 0 ? health.assumption.zero_settle + ' 筆結算=0　' : '') +
              (health.assumption?.no_area > 0 ? health.assumption.no_area + ' 筆無面積' : '') ||
              '資料完整'
            }
            color="var(--primary-500)"/>
          <KPI label="造價分析"
            value={health.cost?.total || 0}
            sub={
              (health.cost?.zero_settle > 0 ? health.cost.zero_settle + ' 筆結算=0　' : '') +
              (health.cost?.no_area > 0 ? health.cost.no_area + ' 筆無面積' : '') ||
              '資料完整'
            }
            color="var(--primary-500)"/>
          <KPI label="DB 大小"
            value={Math.round((health.db_size || 0) / 1024) + ' KB'}
            sub={'最近備份 ' + (health.backups?.length > 0 ? health.backups[0].date : '無')}
            color="var(--muted)"/>
        </div>
      )}

      {/* ── Problem alerts ── */}
      {health?.problems?.length > 0 && (
        <Card title="資料品質問題" accent="var(--warn)" style={{marginBottom:16}}>
          {health.problems.map((p, i) => (
            <div key={i} className="alert alert-warning" style={{marginBottom: i < health.problems.length - 1 ? 8 : 0}}>
              <span className="alert-dot"/>
              <div className="alert-body">
                <strong>{p.name}</strong>
                <span className="muted" style={{marginLeft:8, fontSize:12}}>
                  {p.source === 'cost' ? '造價分析' : '假設工程'} · {p.date}
                </span>
                <span style={{marginLeft:8, color:'var(--warn)', fontSize:12, fontWeight:600}}>
                  {p.issue === 'settle=0' ? '結算金額為 0（需重新上傳 Excel）' : '面積未設定'}
                </span>
              </div>
            </div>
          ))}
        </Card>
      )}

      {/* ── Tab bar + Backup button ── */}
      <div className="row-between" style={{marginBottom:16, flexWrap:'wrap', gap:12}}>
        <Tabs tabs={[
          {key:'assumption_snapshots', label:'假設工程', count: isAssumption ? snapshots.length : undefined},
          {key:'cost_snapshots', label:'造價分析', count: !isAssumption ? snapshots.length : undefined},
        ]} active={table} onChange={setTable}/>

        <Btn kind="ghost" icon={ICONS.zap}
          onClick={handleBackup} disabled={backing}>
          {backing ? '備份中...' : '備份資料庫'}
        </Btn>
      </div>

      {/* Backup message */}
      {backupMsg && (
        <div className={'alert ' + (backupMsg.ok ? 'alert-success' : 'alert-warning')} style={{marginBottom:16}}>
          <span className="alert-dot"/>
          <div className="alert-body">{backupMsg.text}</div>
        </div>
      )}

      {/* ── Snapshot table ── */}
      {loading ? (
        <div className="empty"><h4>載入中...</h4></div>
      ) : snapshots.length > 0 ? (
        <Card title="快照清單" accent="var(--primary-500)" className="card-flush">
          <div className="table-scroll" style={{maxHeight:'unset'}}>
            <table className="table">
              <thead>
                <tr>
                  <th>專案</th>
                  <th>截止日</th>
                  <th>類型</th>
                  <th className="right">結算</th>
                  <th className="right">{isAssumption ? '預算' : '面積 (坪)'}</th>
                  <th className="right">萬/坪</th>
                  <th style={{width:100}}/>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s, i) => {
                  var settle = s.total_settle || 0;
                  var area = s.area_ping || 0;
                  var perPing = (area > 0 && settle > 0) ? (settle / area / 10000).toFixed(2) : '—';
                  var hasIssue = settle === 0 || area === 0;
                  return (
                    <tr key={s.id || i} style={hasIssue ? {background:'var(--warn-bg, #fff8f0)'} : undefined}>
                      <td className="col-name">
                        <span className={'status-dot ' + (hasIssue ? 'status-warning' : 'status-active')}
                          style={{marginRight:6}}/>
                        {s.display_name}
                        {settle === 0 && (
                          <span style={{marginLeft:6, fontSize:10, color:'var(--warn)', fontWeight:600}}>結算=0</span>
                        )}
                      </td>
                      <td className="mono" style={{fontSize:12, color:'var(--muted)'}}>
                        {s.file_date || s.read_date || s.created_at?.slice(0,10) || '—'}
                      </td>
                      <td><Pill tone="muted">{s.project_type || '—'}</Pill></td>
                      <td className="num">{formatTWD(settle)}</td>
                      <td className="num">
                        {isAssumption ? formatTWD(s.total_budget) : (area > 0 ? area.toLocaleString() : '—')}
                      </td>
                      <td className="num" style={{fontFamily:'var(--font-mono)', color:'var(--primary-600)'}}>
                        {perPing}
                      </td>
                      <td>
                        <div className="row" style={{gap:4, justifyContent:'flex-end'}}>
                          {!isAssumption && s.id && (
                            <button className="icon-btn" title="下載 Excel"
                              onClick={() => handleDownload(s.id)}
                              dangerouslySetInnerHTML={{__html: ICONS.download}}/>
                          )}
                          <button className="icon-btn" title="刪除"
                            onClick={() => handleDelete(s.id)}
                            style={{color:'var(--bad)'}}
                            dangerouslySetInnerHTML={{__html: ICONS.close}}/>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <EmptyState
          title="尚無快照"
          sub={isAssumption ? '匯入 KG 一覽表以新增假設工程快照' : '上傳造價 Excel 以新增造價快照'}
          action={
            <Btn kind="primary" icon={ICONS.upload}
              onClick={() => setPage(isAssumption ? 'assumption' : 'cost')}>
              前往匯入
            </Btn>
          }/>
      )}

      {/* ── Backup history ── */}
      {health?.backups?.length > 0 && (
        <div style={{marginTop:24}}>
          <Card title="備份記錄" accent="var(--muted)">
            <div className="stack" style={{gap:6}}>
              {health.backups.map((b, i) => (
                <div key={i} className="row-between" style={{padding:'6px 0', fontSize:12.5}}>
                  <span className="mono">{b.filename}</span>
                  <span>
                    <span className="muted">{b.date}</span>
                    <span className="mono muted" style={{marginLeft:12}}>
                      {Math.round(b.size / 1024)} KB
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── DB info card ── */}
      <div style={{marginTop:16}}>
        <Card title="快照管理" accent="var(--accent)">
          <div className="alert alert-info">
            <span className="alert-dot"/>
            <div className="alert-body">
              <strong>SQLite 儲存</strong>　所有快照含原始 Excel 二進位皆儲存於 kg_history.db，
              複製此檔即可移植至新電腦。點擊「備份資料庫」可建立帶時間戳記的備份副本。
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

Object.assign(window, { PageHistory });
