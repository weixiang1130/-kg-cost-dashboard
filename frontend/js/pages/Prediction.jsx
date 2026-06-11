// 投標預估 — 三法三角驗證（時間調整單價法 / 回歸法 / 分項組合法）
const { useState: useStateP, useEffect: useEffectP, useCallback: useCallbackP, useMemo: useMemoP } = React;

const PROJECT_TYPES = ['FAB', 'CUP', 'OFFICE', '物流中心'];
const STRUCT_TYPES = ['', 'RC', 'SC', 'SRC'];
const CONTRACT_MODES = ['', '總價承攬', '實作實算', '成本加酬金'];
const SUPPLY_MODES = ['', '無', '鋼筋', '鋼構', '其他'];

const CONF_META = {
  high:    { label: '高',     tone: 'good' },
  mid:     { label: '中',     tone: 'warn' },
  low:     { label: '低',     tone: 'warn' },
  minimal: { label: '僅供參考', tone: 'bad' },
};

const METHOD_META = {
  unit_price: { name: '單價法', desc: '物價調整 × 相似度加權中位數' },
  regression: { name: '回歸法', desc: '面積回歸（調整後金額）' },
  component:  { name: '分項法', desc: '分類單價組合 × 結構係數' },
};

function PagePrediction({ setPage }) {
  const [area, setArea] = useStateP(22000);
  const [projType, setProjType] = useStateP('FAB');
  const [structType, setStructType] = useStateP('');
  const [contractMode, setContractMode] = useStateP('');
  const [withMaterial, setWithMaterial] = useStateP('');
  const [escalate, setEscalate] = useStateP(true);
  const [matRef, setMatRef] = useStateP(null);       // 現行參考行情 {rebar, concrete}
  const [showPriceMgr, setShowPriceMgr] = useStateP(false);
  const [tab, setTab] = useStateP('cost');
  const [method, setMethod] = useStateP('blended');
  const [data, setData] = useStateP(null);
  const [loading, setLoading] = useStateP(false);
  const [error, setError] = useStateP(null);

  // 載入今日參考行情（顯示用）
  const loadMatRef = useCallbackP(async () => {
    try {
      const r = await API.getMaterialPrices();
      const year = String(new Date().getFullYear());
      const pick = tbl => {
        const ys = Object.keys(tbl || {}).sort();
        return tbl?.[year] ?? (ys.length ? tbl[ys[ys.length - 1]] : 0);
      };
      setMatRef({
        rebar: pick(r.prices?.rebar),
        concrete: pick(r.prices?.concrete),
        raw: r.prices,
      });
    } catch (e) { /* 參考行情載入失敗不阻擋預估 */ }
  }, []);
  useEffectP(() => { loadMatRef(); }, [loadMatRef]);

  const fetchPrediction = useCallbackP(async () => {
    setLoading(true);
    setError(null);
    try {
      // 投標階段尚未詢價，直接採現行行情：物價指數調整已自動反映，不另做價格偏差
      const raw = await API.getPrediction(projType, area, {
        structType, contractMode, withMaterial, escalate,
      });
      if (!raw.cost_ensemble && !raw.assumption_ensemble) {
        setError('此類型無足夠歷史資料（至少需 1 筆含面積的快照）');
        setData(null);
        return;
      }
      setData({ cost: raw.cost_ensemble, assumption: raw.assumption_ensemble });
    } catch (e) {
      setError(e.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [projType, area, structType, contractMode, withMaterial, escalate]);

  useEffectP(() => {
    const timer = setTimeout(fetchPrediction, 400);
    return () => clearTimeout(timer);
  }, [fetchPrediction]);

  const ens = data ? (tab === 'cost' ? data.cost : data.assumption) : null;
  const conf = ens ? (CONF_META[ens.confidence] || CONF_META.minimal) : null;
  const blended = ens?.blended;
  const perPing = blended && area > 0 ? blended.predicted / area : 0;

  const tabs = [];
  if (data?.cost) tabs.push({ key: 'cost', label: '造價預估', count: data.cost.n });
  if (data?.assumption) tabs.push({ key: 'assumption', label: '假設工程預估', count: data.assumption.n });

  useEffectP(() => {
    if (data && !ens && tabs.length > 0) setTab(tabs[0].key);
  }, [data]);

  const methods = ens?.methods || {};
  const mReg = methods.regression;
  const regHistory = useMemoP(() => {
    if (!mReg || !ens) return [];
    const outliers = new Set(mReg.outliers || []);
    return (mReg.history_x || []).map((x, i) => ({
      area: x, cost: (mReg.history_y || [])[i] || 0,
      display_name: (ens.cases || [])[i]?.display_name || `案例 ${i+1}`,
      outlier: outliers.has(i),
    }));
  }, [mReg, ens]);

  return (
    <>
      <TopBar
        title="投標預估"
        breadcrumb="總覽 / 投標預估"
        subtitle="三法三角驗證：物價調整單價法 × 回歸法 × 分項組合法．依結構型式與發包條件加權"
      />

      {ens && !loading && (
        <div className="grid grid-4" style={{marginBottom:16}}>
          <KPI label={tab === 'cost' ? '綜合建議造價' : '綜合建議假設工程'}
            value={formatTWD(blended.predicted)}
            sub={`區間 ${formatTWD(blended.low)} ～ ${formatTWD(blended.high)}`}/>
          <KPI label="建議單價" value={`${(perPing/10000).toFixed(2)} 萬/坪`}
            sub={escalate ? '已反映物價至今日' : '未做物價調整'}/>
          <KPI label="樣本數" value={`${ens.n} 筆`}
            sub={methods.unit_price ? `有效樣本 ${methods.unit_price.n_eff}（相似度加權後）` : '—'}/>
          <KPI label="預估信心" value={conf.label} tone={conf.tone}
            sub={`三法收斂度檢核`}/>
        </div>
      )}

      <div className="grid grid-2" style={{marginBottom:16}}>
        <Card title="專案條件" accent="var(--primary-500)">
          <div className="stack-lg">
            <div className="field">
              <label className="field-label">面積（坪）</label>
              <div className="row" style={{gap:8}}>
                <input className="field-input num" style={{flex:1, fontSize:16, fontWeight:600}}
                  type="number" value={area} onChange={e => setArea(+e.target.value)}/>
                <span className="muted" style={{fontSize:11, fontFamily:'var(--font-mono)'}}>
                  ≈ {Math.round(area * 3.30579).toLocaleString()} m²
                </span>
              </div>
              <input type="range" min="5000" max="35000" step="500"
                value={area} onChange={e => setArea(+e.target.value)}
                style={{width:'100%', marginTop:8, accentColor:'var(--primary-500)'}}/>
            </div>

            <div className="grid grid-2" style={{gap:12}}>
              <div className="field">
                <label className="field-label">類型</label>
                <select className="field-input" value={projType} onChange={e => setProjType(e.target.value)}>
                  {PROJECT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="field">
                <label className="field-label">結構型式</label>
                <select className="field-input" value={structType} onChange={e => setStructType(e.target.value)}>
                  {STRUCT_TYPES.map(t => <option key={t} value={t}>{t || '不指定'}</option>)}
                </select>
              </div>
              <div className="field">
                <label className="field-label">發包方式</label>
                <select className="field-input" value={contractMode} onChange={e => setContractMode(e.target.value)}>
                  {CONTRACT_MODES.map(t => <option key={t} value={t}>{t || '不指定'}</option>)}
                </select>
              </div>
              <div className="field">
                <label className="field-label">業主供料</label>
                <select className="field-input" value={withMaterial} onChange={e => setWithMaterial(e.target.value)}>
                  {SUPPLY_MODES.map(t => <option key={t} value={t}>{t || '不指定'}</option>)}
                </select>
              </div>
            </div>

            <label className="row" style={{gap:8, cursor:'pointer', fontSize:12.5}}>
              <input type="checkbox" checked={escalate} onChange={e => setEscalate(e.target.checked)}
                style={{accentColor:'var(--primary-500)'}}/>
              物價指數調整（將歷史結算調整到今日幣值）
            </label>

            <div className="divider"/>
            <div className="row-between">
              <div className="section-label" style={{margin:0}}>本次預估採用的行情基準</div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowPriceMgr(true)}>
                參考行情管理
              </button>
            </div>

            <div style={{
              display:'grid', gridTemplateColumns:'1fr 1fr', gap:10,
              padding:'10px 12px', background:'var(--surface-2)',
              border:'1px solid var(--border)', borderRadius:10,
            }}>
              <div>
                <div className="muted" style={{fontSize:10.5}}>鋼筋（SD420W）</div>
                <div className="num" style={{fontSize:14, fontWeight:700}}>
                  {matRef?.rebar ? Math.round(matRef.rebar).toLocaleString() : '—'}
                  <span className="muted" style={{fontSize:10, fontWeight:400}}> 元/噸</span>
                </div>
              </div>
              <div>
                <div className="muted" style={{fontSize:10.5}}>預拌混凝土（3000psi）</div>
                <div className="num" style={{fontSize:14, fontWeight:700}}>
                  {matRef?.concrete ? Math.round(matRef.concrete).toLocaleString() : '—'}
                  <span className="muted" style={{fontSize:10, fontWeight:400}}> 元/m³</span>
                </div>
              </div>
            </div>

            <div className="muted" style={{fontSize:10.5, lineHeight:1.6}}>
              投標階段尚未詢價，預估直接採現行行情：歷史結算已按營造物價指數自動調整至今日水準，
              上方參考價為本次預估的行情前提。行情表來源：豐興週牌價 / 中鋼盤價 / 主計處營造物價月報，
              建議每月校正一次。
            </div>
          </div>
        </Card>

        <Card title="預估結果" accent="var(--accent)"
          action={ens && conf && <Pill tone={conf.tone}>信心：{conf.label}</Pill>}>
          {loading && <div className="muted" style={{padding:24, textAlign:'center'}}>計算中...</div>}
          {error && (
            <div className="alert alert-warning" style={{marginBottom:12}}>
              <span className="alert-dot"/>
              <div className="alert-body"><strong>無法預估</strong>　{error}</div>
            </div>
          )}
          {ens && !loading && (
            <>
              {tabs.length > 1 && (
                <div style={{marginBottom:14}}>
                  <Tabs tabs={tabs} active={tab} onChange={setTab}/>
                </div>
              )}

              <div style={{marginBottom:4}}>
                <div className="muted" style={{fontSize:11.5, letterSpacing:.8, textTransform:'uppercase', fontWeight:600}}>
                  綜合建議值（三法加權）
                </div>
                <div className="big-num" style={{marginTop:6}}>{formatTWD(blended.predicted)}</div>
                <div className="num muted" style={{fontSize:12, marginTop:4}}>
                  ≈ {(perPing / 10000).toFixed(2)} 萬/坪
                </div>
              </div>

              {blended.high > blended.low && (
                <div style={{padding:'12px 0 4px'}}>
                  <div className="row-between muted" style={{fontSize:11.5, marginBottom:6}}>
                    <span>建議投標區間</span>
                    <span className="mono">{formatTWD(blended.low)} ～ {formatTWD(blended.high)}</span>
                  </div>
                  <ConfidenceBar low={blended.low} mid={blended.predicted} high={blended.high}/>
                </div>
              )}

              {ens.confidence_note && (
                <div className="muted" style={{fontSize:11, marginTop:6}}>ⓘ {ens.confidence_note}</div>
              )}

              <div className="divider" style={{margin:'14px 0'}}/>
              <div className="section-label">三法比較（點選看明細）</div>
              <div className="grid grid-3" style={{gap:10}}>
                {Object.entries(METHOD_META).map(([key, meta]) => {
                  const m = methods[key];
                  if (!m) return (
                    <div key={key} className="method-card muted" style={{
                      border:'1px dashed var(--border)', borderRadius:10, padding:'10px 12px', fontSize:11
                    }}>
                      {meta.name}：資料不足
                    </div>
                  );
                  const active = method === key;
                  const wt = ens.blend_weights?.[key];
                  return (
                    <button key={key} onClick={() => setMethod(active ? 'blended' : key)}
                      style={{
                        textAlign:'left', cursor:'pointer', borderRadius:10, padding:'10px 12px',
                        border: active ? '1.5px solid var(--primary-500)' : '1px solid var(--border)',
                        background: active ? 'var(--primary-50)' : 'var(--surface)',
                        transition:'all .15s',
                      }}>
                      <div className="row-between">
                        <span style={{fontSize:11.5, fontWeight:700}}>{meta.name}</span>
                        {wt != null && <span className="muted" style={{fontSize:10}}>權重 {(wt*100).toFixed(0)}%</span>}
                      </div>
                      <div className="num" style={{fontSize:15, fontWeight:700, margin:'4px 0 2px'}}>
                        {formatTWD(m.predicted)}
                      </div>
                      <div className="muted" style={{fontSize:10, lineHeight:1.4}}>{meta.desc}</div>
                      {key === 'regression' && m.warning && (
                        <div style={{fontSize:10, color:'var(--warn)', marginTop:4}}>⚠ 斜率異常</div>
                      )}
                    </button>
                  );
                })}
              </div>

              {method === 'regression' && mReg && (
                <div style={{marginTop:14}}>
                  {mReg.warning && (
                    <div className="alert alert-warning" style={{marginBottom:10}}>
                      <span className="alert-dot"/>
                      <div className="alert-body"><strong>回歸警告</strong>　{mReg.warning}</div>
                    </div>
                  )}
                  {mReg.extrapolation && (
                    <div className="alert alert-warning" style={{marginBottom:10}}>
                      <span className="alert-dot"/>
                      <div className="alert-body">
                        <strong>外插警告</strong>　目標面積超出歷史範圍
                        （{Math.round(mReg.x_min).toLocaleString()} ～ {Math.round(mReg.x_max).toLocaleString()} 坪）
                      </div>
                    </div>
                  )}
                  {mReg.slope != null && regHistory.length > 0 && (
                    <>
                      <RegressionChart
                        history={regHistory}
                        regression={{slope:mReg.slope, intercept:mReg.intercept, se:mReg.se||0, r2:mReg.r2}}
                        predictX={area} predictY={mReg.predicted}
                        band={mReg.pi_band} dataXMax={mReg.x_max}
                        color="var(--primary-500)" accentColor="var(--accent)" h={300}/>
                      <div className="muted" style={{fontSize:10.5, marginTop:6}}>
                        R² {mReg.r2?.toFixed(3)}
                        {mReg.r2_adj != null ? ` · 調整後 ${mReg.r2_adj.toFixed(3)}` : ''}
                        　·　金額已做物價調整　·　區間 = t 分佈 95% 預測區間
                      </div>
                    </>
                  )}
                </div>
              )}

              {method === 'component' && methods.component && (
                <div style={{marginTop:14}}>
                  <BarChart
                    data={methods.component.items.filter(i => i.amount > 0).map(i => ({
                      key: i.name, label: i.name, value: i.amount,
                      color: i.name === '結構工程' ? 'var(--primary-500)' : 'var(--primary-300)',
                    }))}
                    h={Math.max(180, methods.component.items.length * 38)}
                    color="var(--primary-300)" accentColor="var(--primary-500)"/>
                  <div className="muted" style={{fontSize:10.5, marginTop:6}}>
                    各分類加權單價 × {area.toLocaleString()} 坪加總
                    {methods.component.struct_factor_applied && '　·　結構工程已按結構型式係數調整（RC 1.00 / SC 1.15 / SRC 1.30）'}
                  </div>
                </div>
              )}

              {method === 'unit_price' && methods.unit_price && (
                <div className="muted" style={{fontSize:11.5, marginTop:14, lineHeight:1.7}}>
                  加權中位單價 <b className="num">{Math.round(methods.unit_price.per_ping).toLocaleString()}</b> 元/坪
                  × {area.toLocaleString()} 坪；
                  區間取加權 P20 ～ P80（{formatTWD(methods.unit_price.low)} ～ {formatTWD(methods.unit_price.high)}）。
                  權重 = 時間遠近 × 面積規模 × 結構型式 × 發包條件相似度，明細見下表。
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {ens && !loading && ens.cases?.length > 0 && (
        <Card title="歷史案例與相似度權重" accent="var(--primary-300)"
          action={<span className="muted" style={{fontSize:11}}>
            調整後單價 = 結算 ÷ 面積 × 物價係數；權重越高對預估影響越大
          </span>}>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>專案</th>
                  <th>結算日</th>
                  <th>結構</th>
                  <th className="right">面積（坪）</th>
                  <th className="right">原結算</th>
                  <th className="right">物價係數</th>
                  <th className="right">調整後單價</th>
                  <th className="right">權重</th>
                </tr>
              </thead>
              <tbody>
                {[...ens.cases].sort((a, b) => b.weight - a.weight).map((c, i) => {
                  const maxW = Math.max(...ens.cases.map(x => x.weight)) || 1;
                  return (
                    <tr key={i}>
                      <td className="col-name" style={{fontSize:12}}>{c.display_name}</td>
                      <td className="muted" style={{fontSize:11.5, fontFamily:'var(--font-mono)'}}>{c.read_date || '—'}</td>
                      <td style={{fontSize:11.5}}>{c.struct_type || <span className="muted">未填</span>}</td>
                      <td className="num" style={{fontSize:12}}>{c.area?.toLocaleString()}</td>
                      <td className="num" style={{fontSize:12}}>{formatTWD(c.settle)}</td>
                      <td className="num" style={{fontSize:12}}>×{c.esc_factor?.toFixed(3)}</td>
                      <td className="num" style={{fontSize:12}}>{Math.round(c.esc_pp).toLocaleString()}</td>
                      <td style={{minWidth:90}}>
                        <div className="row" style={{gap:6, alignItems:'center'}}>
                          <div style={{flex:1, height:5, background:'var(--bar-track)', borderRadius:99}}>
                            <div style={{width:`${(c.weight/maxW)*100}%`, height:'100%',
                              background:'var(--primary-400)', borderRadius:99}}/>
                          </div>
                          <span className="num muted" style={{fontSize:10.5}}>{c.weight.toFixed(2)}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="alert alert-info" style={{marginTop:16}}>
            <span className="alert-dot"/>
            <div className="alert-body">
              <strong>提升精度建議</strong>
              　到「歷史記錄」為每筆案例補登<b>結構型式 / 發包方式 / 業主供料</b>，
              相似度加權才能發揮；歷史案例「結構」欄顯示「未填」者目前以中性權重處理。
              業主供料條件不同的案例（如鋼筋甲供）單價會失真，補登後系統會自動降權。
            </div>
          </div>
        </Card>
      )}

      <PriceManagerModal open={showPriceMgr} onClose={() => setShowPriceMgr(false)}
        prices={matRef?.raw} onSaved={loadMatRef}/>
    </>
  );
}

function PriceManagerModal({ open, onClose, prices, onSaved }) {
  const year = String(new Date().getFullYear());
  const [rebar, setRebar] = useStateP('');
  const [concrete, setConcrete] = useStateP('');
  const [saving, setSaving] = useStateP(false);
  const [msg, setMsg] = useStateP('');

  useEffectP(() => {
    if (open && prices) {
      setRebar(prices.rebar?.[year] ?? '');
      setConcrete(prices.concrete?.[year] ?? '');
      setMsg('');
    }
  }, [open, prices]);

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      const body = {};
      if (+rebar > 0) body.rebar = { [year]: +rebar };
      if (+concrete > 0) body.concrete = { [year]: +concrete };
      if (Object.keys(body).length === 0) { setMsg('請至少輸入一項價格'); return; }
      await API.saveMaterialPrices(body);
      setMsg('已儲存');
      onSaved && onSaved();
    } catch (e) {
      setMsg('儲存失敗：' + e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={`參考行情管理（${year} 年）`}
      footer={
        <div className="row" style={{gap:8, justifyContent:'flex-end'}}>
          {msg && <span className="muted" style={{fontSize:12, alignSelf:'center'}}>{msg}</span>}
          <Btn kind="ghost" onClick={onClose}>關閉</Btn>
          <Btn kind="primary" onClick={save} disabled={saving}>{saving ? '儲存中...' : '儲存'}</Btn>
        </div>
      }>
      <div className="stack-lg">
        <div className="field">
          <label className="field-label">鋼筋（SD420W）元/噸</label>
          <input className="field-input num" type="number" value={rebar}
            onChange={e => setRebar(e.target.value)}/>
        </div>
        <div className="field">
          <label className="field-label">預拌混凝土（3000psi）元/m³</label>
          <input className="field-input num" type="number" value={concrete}
            onChange={e => setConcrete(e.target.value)}/>
        </div>
        <div className="alert alert-info">
          <span className="alert-dot"/>
          <div className="alert-body" style={{fontSize:11.5, lineHeight:1.7}}>
            <strong>公開資料來源（建議每月更新一次）</strong><br/>
            ・鋼筋：豐興鋼鐵每週牌價、中鋼內銷盤價<br/>
            ・混凝土：各區拌合廠報價（國產、亞東等）<br/>
            ・物價指數：主計總處「營造工程物價指數」月報（data.gov.tw 可下載）<br/>
            內建值為近似參考，更新後立即反映在偏差計算。
          </div>
        </div>
      </div>
    </Modal>
  );
}

function ConfidenceBar({ low, mid, high }) {
  const pct = high > low ? Math.min(97, Math.max(3, ((mid - low) / (high - low)) * 100)) : 50;
  return (
    <div style={{position:'relative', height:36}}>
      <div style={{
        position:'absolute', top:14, left:0, right:0, height:8,
        background:'linear-gradient(90deg, var(--primary-100), var(--primary-300), var(--primary-100))',
        borderRadius:999, opacity:.8
      }}/>
      <div style={{
        position:'absolute', top:8, left:`${pct}%`, transform:'translateX(-50%)',
        width:4, height:20, background:'var(--accent)', borderRadius:2
      }}/>
      <div style={{position:'absolute', top:32, left:0, fontSize:10.5, color:'var(--muted)', fontFamily:'var(--font-mono)'}}>
        {formatTWD(low)}
      </div>
      <div style={{position:'absolute', top:32, right:0, fontSize:10.5, color:'var(--muted)', fontFamily:'var(--font-mono)'}}>
        {formatTWD(high)}
      </div>
      <div style={{
        position:'absolute', top:-2, left:`${pct}%`, transform:'translateX(-50%)',
        fontSize:10.5, color:'var(--accent)', fontWeight:700, fontFamily:'var(--font-mono)', whiteSpace:'nowrap'
      }}>
        ▼ {formatTWD(mid)}
      </div>
    </div>
  );
}

Object.assign(window, { PagePrediction });
