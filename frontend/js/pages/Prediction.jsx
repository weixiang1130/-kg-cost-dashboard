// 投標預估 — 回歸預估 + What-if slider + 信賴區間
const { useState: useStateP, useEffect: useEffectP, useCallback: useCallbackP } = React;

const PROJECT_TYPES = ['FAB', 'CUP', 'OFFICE', '物流中心'];

function PagePrediction({ setPage }) {
  const [area, setArea] = useStateP(22000);
  const [projType, setProjType] = useStateP('FAB');
  const [prediction, setPrediction] = useStateP(null);
  const [loading, setLoading] = useStateP(false);
  const [error, setError] = useStateP(null);
  const [whatIf, setWhatIf] = useStateP({ rebar: 0, concrete: 0, labor: 0 });

  const fetchPrediction = useCallbackP(async () => {
    setLoading(true);
    setError(null);
    try {
      const raw = await API.getPrediction(projType, area);
      const cp = raw.cost_prediction;
      if (!cp) { setError('此類型無足夠資料'); setPrediction(null); return; }
      const se = cp.se || 0;
      const hist = (cp.history_x || []).map((x, i) => ({
        area: x, cost: (cp.history_y || [])[i] || 0,
        display_name: (raw.history_cost || [])[i]?.display_name || `案例 ${i+1}`,
      }));
      setPrediction({
        predicted: cp.predicted, r2: cp.r2, slope: cp.slope, intercept: cp.intercept, se: se,
        ci_lower: cp.predicted - 1.96 * se, ci_upper: cp.predicted + 1.96 * se,
        history: hist,
      });
    } catch (e) {
      setError(e.message);
      setPrediction(null);
    } finally {
      setLoading(false);
    }
  }, [projType, area]);

  useEffectP(() => {
    const timer = setTimeout(fetchPrediction, 400);
    return () => clearTimeout(timer);
  }, [fetchPrediction]);

  const adjustment = 1 + (whatIf.rebar * 0.0008 + whatIf.concrete * 0.0006 + whatIf.labor * 0.004);
  const predicted = prediction ? prediction.predicted * adjustment : 0;
  const lower = prediction ? prediction.ci_lower * adjustment : 0;
  const upper = prediction ? prediction.ci_upper * adjustment : 0;

  return (
    <>
      <TopBar
        title="投標預估"
        breadcrumb="總覽 / 投標預估"
        subtitle="依專案類型 + 面積回歸預估造價．含 95% 信賴區間與 What-if 試算"
      />

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
              <div className="row-between muted" style={{fontSize:10.5, fontFamily:'var(--font-mono)'}}>
                <span>5,000</span><span>20,000</span><span>35,000</span>
              </div>
            </div>

            <div className="field">
              <label className="field-label">類型</label>
              <select className="field-input" value={projType} onChange={e => setProjType(e.target.value)}>
                {PROJECT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div className="divider"/>
            <div className="section-label" style={{margin:0}}>What-if · 行情敏感度</div>
            <PredSlider label="鋼筋指數" value={whatIf.rebar} min={-20} max={20} unit="%"
              onChange={v => setWhatIf({...whatIf, rebar: v})}/>
            <PredSlider label="混凝土指數" value={whatIf.concrete} min={-20} max={20} unit="%"
              onChange={v => setWhatIf({...whatIf, concrete: v})}/>
            <PredSlider label="工資指數" value={whatIf.labor} min={-15} max={20} unit="%"
              onChange={v => setWhatIf({...whatIf, labor: v})}/>
          </div>
        </Card>

        <Card title="預估結果" accent="var(--accent)"
          action={prediction && (
            <Pill tone="good">
              R² = {prediction.r2?.toFixed(3)}　信心：{prediction.r2 >= 0.9 ? '高' : prediction.r2 >= 0.7 ? '中' : '低'}
            </Pill>
          )}>
          {loading && <div className="muted" style={{padding:24, textAlign:'center'}}>計算中...</div>}
          {error && (
            <div className="alert alert-warning" style={{marginBottom:12}}>
              <span className="alert-dot"/>
              <div className="alert-body">
                <strong>無法預估</strong>　{error}
                <div className="muted" style={{fontSize:11, marginTop:4}}>
                  可能原因：此類型歷史資料不足 2 筆
                </div>
              </div>
            </div>
          )}
          {prediction && !loading && (
            <>
              <div className="row" style={{gap:24, alignItems:'baseline', marginBottom:8}}>
                <div>
                  <div className="muted" style={{fontSize:11.5, letterSpacing:.8, textTransform:'uppercase', fontWeight:600}}>
                    預估造價
                  </div>
                  <div className="big-num" style={{marginTop:6}}>{formatTWD(predicted)}</div>
                  <div className="num muted" style={{fontSize:12, marginTop:4}}>
                    ≈ {area > 0 ? (predicted / area / 10000).toFixed(2) : '—'} 萬/坪
                  </div>
                </div>
                <div style={{flex:1, textAlign:'right'}}>
                  <Pill tone={adjustment > 1.02 ? 'warn' : adjustment < 0.98 ? 'good' : 'muted'}>
                    What-if 調整 {((adjustment - 1) * 100).toFixed(1)}%
                  </Pill>
                </div>
              </div>

              <div style={{padding:'14px 0 6px'}}>
                <div className="row-between muted" style={{fontSize:11.5, marginBottom:6}}>
                  <span>95% 信賴區間</span>
                  <span className="mono">{formatTWD(lower)} ～ {formatTWD(upper)}</span>
                </div>
                <ConfidenceBar low={lower} mid={predicted} high={upper}/>
              </div>

              {prediction.history && prediction.history.length > 0 && (
                <>
                  <RegressionChart
                    history={prediction.history}
                    regression={{slope:prediction.slope, intercept:prediction.intercept, se:prediction.se||0, r2:prediction.r2}}
                    predictX={area}
                    predictY={predicted}
                    color="var(--primary-500)"
                    accentColor="var(--accent)"
                    h={320}/>

                  <div className="legend" style={{marginTop:8, justifyContent:'center'}}>
                    <span><span className="legend-dot" style={{background:'var(--primary-300)', opacity:.35}}/>95% 信賴帶</span>
                    <span><span className="legend-dot" style={{background:'var(--primary-500)'}}/>回歸線</span>
                    <span><span className="legend-dot" style={{background:'var(--accent)'}}/>本次預估</span>
                  </div>
                </>
              )}

              {prediction.history && prediction.history.length > 0 && (
                <div style={{marginTop:20}}>
                  <h3 className="section-label">同類專案明細</h3>
                  <div className="table-scroll">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>專案</th>
                          <th className="right">面積</th>
                          <th className="right">造價</th>
                          <th className="right">元/坪</th>
                        </tr>
                      </thead>
                      <tbody>
                        {prediction.history.map((p, i) => {
                          const closest = Math.abs(p.area - area) < 3000;
                          return (
                            <tr key={i} className={closest ? 'row-active' : ''}>
                              <td className="col-name" style={{fontSize:12}}>{p.display_name || p.name}</td>
                              <td className="num" style={{fontSize:12}}>{p.area?.toLocaleString()}</td>
                              <td className="num" style={{fontSize:12}}>{formatTWD(p.cost)}</td>
                              <td className="num" style={{fontSize:12}}>
                                {p.area > 0 ? Math.round(p.cost / p.area).toLocaleString() : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="alert alert-info" style={{marginTop:16}}>
                <span className="alert-dot"/>
                <div className="alert-body">
                  <strong>R² 判讀</strong>
                  {prediction.r2 >= 0.9 ? '　0.9 以上：模型極可靠，可作為投標主要依據' :
                    prediction.r2 >= 0.7 ? '　0.7-0.9：模型可靠，配合條件判讀' :
                      '　< 0.7：僅供參考，建議補充樣本'}
                </div>
              </div>
            </>
          )}
        </Card>
      </div>
    </>
  );
}

function PredSlider({ label, value, min, max, unit = '', onChange }) {
  return (
    <div className="field">
      <div className="row-between">
        <label className="field-label">{label}</label>
        <span className="num" style={{
          fontSize:12, fontWeight:600,
          color: value === 0 ? 'var(--muted)' : value > 0 ? 'var(--warn)' : 'var(--good)'
        }}>
          {value > 0 ? '+' : ''}{value}{unit}
        </span>
      </div>
      <input type="range" min={min} max={max} value={value}
        onChange={e => onChange(+e.target.value)}
        style={{width:'100%', marginTop:4, accentColor:'var(--primary-500)'}}/>
    </div>
  );
}

function ConfidenceBar({ low, mid, high }) {
  return (
    <div style={{position:'relative', height:36}}>
      <div style={{
        position:'absolute', top:14, left:0, right:0, height:8,
        background:'linear-gradient(90deg, var(--primary-100), var(--primary-300), var(--primary-100))',
        borderRadius:999, opacity:.8
      }}/>
      <div style={{
        position:'absolute', top:8, left:'50%', transform:'translateX(-50%)',
        width:4, height:20, background:'var(--accent)', borderRadius:2
      }}/>
      <div style={{position:'absolute', top:32, left:0, fontSize:10.5, color:'var(--muted)', fontFamily:'var(--font-mono)'}}>
        {formatTWD(low)}
      </div>
      <div style={{position:'absolute', top:32, right:0, fontSize:10.5, color:'var(--muted)', fontFamily:'var(--font-mono)'}}>
        {formatTWD(high)}
      </div>
      <div style={{
        position:'absolute', top:-2, left:'50%', transform:'translateX(-50%)',
        fontSize:10.5, color:'var(--accent)', fontWeight:700, fontFamily:'var(--font-mono)'
      }}>
        ▼ {formatTWD(mid)}
      </div>
    </div>
  );
}

Object.assign(window, { PagePrediction });
