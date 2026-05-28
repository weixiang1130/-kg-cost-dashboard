// 假設工程分析 — 上傳 KG、面積設定、13 項目明細、趨勢追蹤
const { useState: useStateA, useEffect: useEffectA, useRef: useRefA } = React;

const KG_ITEMS = [
  '租工', '打石工', '技術工', '零星建材', '雜項工程', '機具租金',
  '安衛零星', '雜支一', '雜支二', '水費', '電費', '電話費', '人員薪資',
];

function PageAssumption({ setPage }) {
  const [projects, setProjects] = useStateA([]);
  const [selectedDn, setSelectedDn] = useStateA(null);
  const [snapshots, setSnapshots] = useStateA([]);
  const [parseResult, setParseResult] = useStateA(null);
  const [parsing, setParsing] = useStateA(false);
  const [saving, setSaving] = useStateA(false);
  const [activeTab, setActiveTab] = useStateA('analysis');
  // Area input for upload
  const [areaInput, setAreaInput] = useStateA(0);
  const [typeInput, setTypeInput] = useStateA('其他');
  // Area editing for saved snapshots
  const [editingArea, setEditingArea] = useStateA(false);
  const [editAreaVal, setEditAreaVal] = useStateA(0);
  const [savingArea, setSavingArea] = useStateA(false);
  const fileRef = useRefA(null);

  useEffectA(() => {
    API.getProjects().then(data => {
      const names = (data?.projects || []).filter(p => p.assumption_count > 0).map(p => p.display_name);
      setProjects(names);
      if (names.length > 0 && !selectedDn) setSelectedDn(names[0]);
    }).catch(() => {});
  }, []);

  useEffectA(() => {
    if (!selectedDn) return;
    setEditingArea(false);
    API.getAssumption(selectedDn).then(data => {
      setSnapshots(data?.snapshots || []);
    }).catch(() => setSnapshots([]));
  }, [selectedDn]);

  async function handleUpload(files) {
    setParsing(true);
    setParseResult(null);
    try {
      const result = await API.parseKG(files);
      const items = result?.results || [];
      const first = items.find(r => !r.error);
      if (!first) {
        const errMsg = items[0]?.error || '無法解析檔案';
        alert('解析失敗：' + errMsg);
        return;
      }
      setParseResult(first);
      setTypeInput(first.detected_type || '其他');
      // Try to get saved area
      try {
        const areas = await API.getAreas();
        const savedArea = areas?.[first.display_name] || 0;
        setAreaInput(savedArea);
      } catch(e) { setAreaInput(0); }
    } catch (e) {
      alert('解析失敗：' + e.message);
    } finally {
      setParsing(false);
    }
  }

  async function handleSave() {
    if (!parseResult) return;
    setSaving(true);
    try {
      const payload = {
        display_name: parseResult.display_name,
        project_full: parseResult.project_full || '',
        cutoff_date: parseResult.cutoff || '',
        area_ping: areaInput,
        total_budget: parseResult.total_budget || 0,
        total_settle: parseResult.total_settle || 0,
        items: parseResult.items || {},
        source_filename: parseResult.filename || '',
        file_date: parseResult.file_date || '',
        project_type: typeInput,
        conditions: {},
      };
      await API.saveAssumption(payload);
      // Save area
      if (areaInput > 0) {
        try {
          const areas = await API.getAreas();
          areas[parseResult.display_name] = areaInput;
          await API.saveAreas(areas);
        } catch(e) {}
      }
      setParseResult(null);
      // Reload
      const data = await API.getProjects();
      const names = (data?.projects || []).filter(p => p.assumption_count > 0).map(p => p.display_name);
      setProjects(names);
      setSelectedDn(parseResult.display_name);
    } catch (e) {
      alert('儲存失敗：' + e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdateArea(snap) {
    setSavingArea(true);
    try {
      await API.updateAssumptionArea(snap.id, editAreaVal, selectedDn);
      // Reload snapshots
      const data = await API.getAssumption(selectedDn);
      setSnapshots(data?.snapshots || []);
      setEditingArea(false);
    } catch (e) {
      alert('面積更新失敗：' + e.message);
    } finally {
      setSavingArea(false);
    }
  }

  const latestSnap = snapshots[snapshots.length - 1];
  const prevSnap = snapshots.length > 1 ? snapshots[snapshots.length - 2] : null;

  // Unit cost helpers
  function unitCostPing(total, area) {
    if (!area || area <= 0) return null;
    return total / area / 10000; // 萬/坪
  }
  function unitCostM2(total, area) {
    if (!area || area <= 0) return null;
    var m2 = area / 0.3025;
    return total / m2; // 元/m²
  }

  return React.createElement(React.Fragment, null,
    React.createElement(TopBar, {
      title: "假設工程分析",
      breadcrumb: "總覽 / 假設工程分析",
      subtitle: "上傳 KG 一覽表．設定面積．13 項假設工程結算追蹤",
      actions: React.createElement(React.Fragment, null,
        React.createElement(Btn, {kind:"primary", icon:ICONS.upload, onClick:() => fileRef.current?.click()}, "匯入假設工程"),
        React.createElement('input', {ref:fileRef, type:'file', accept:'.xlsx,.xls', multiple:true,
          style:{display:'none'},
          onChange: e => { if (e.target.files.length > 0) handleUpload(Array.from(e.target.files)); }
        })
      )
    }),

    /* Parsing indicator */
    parsing && React.createElement('div', {className:'alert alert-info', style:{marginBottom:16}},
      React.createElement('span', {className:'alert-dot'}),
      React.createElement('div', {className:'alert-body'},
        React.createElement('strong', null, '解析中...'), ' 正在讀取上傳的 Excel'
      )
    ),

    /* ========== Upload result + area input panel ========== */
    parseResult && !parsing && React.createElement(Card, {
      title: '解析結果 — 設定面積後儲存',
      accent: 'var(--accent)',
      style: {marginBottom:16}
    },
      React.createElement('div', {className:'alert alert-success', style:{marginBottom:16}},
        React.createElement('span', {className:'alert-dot'}),
        React.createElement('div', {className:'alert-body'},
          React.createElement('strong', null, parseResult.display_name),
          ' · 截止日 ', parseResult.file_date,
          ' · 結算 ', formatTWD(parseResult.total_settle),
          ' · 預算 ', formatTWD(parseResult.total_budget)
        )
      ),
      React.createElement('div', {className:'grid grid-3', style:{marginBottom:16, gap:16}},
        /* Area input */
        React.createElement('div', {className:'field'},
          React.createElement('label', {className:'field-label'}, '面積（坪）'),
          React.createElement('input', {className:'field-input num', type:'number', min:0, step:100,
            value: areaInput, onChange: e => setAreaInput(+e.target.value),
            style:{fontSize:16, fontWeight:600}
          }),
          React.createElement('div', {className:'muted', style:{fontSize:11, marginTop:4, fontFamily:'var(--font-mono)'}},
            '≈ ', areaInput > 0 ? Math.round(areaInput / 0.3025).toLocaleString() : '0', ' m²'
          ),
          areaInput > 0 && parseResult.total_settle > 0 && React.createElement('div', {
            style:{marginTop:6, padding:'6px 10px', background:'var(--primary-50)', borderRadius:6, fontSize:12}
          },
            React.createElement('strong', {style:{color:'var(--primary-600)'}},
              '假設工程/坪 ', (parseResult.total_settle / areaInput / 10000).toFixed(2), ' 萬/坪'
            ),
            React.createElement('span', {style:{marginLeft:8, color:'var(--muted)'}},
              '≈ ', Math.round(parseResult.total_settle / (areaInput / 0.3025)).toLocaleString(), ' 元/m²'
            )
          )
        ),
        /* Project type */
        React.createElement('div', {className:'field'},
          React.createElement('label', {className:'field-label'}, '專案類型'),
          React.createElement('select', {className:'field-input', value:typeInput, onChange: e => setTypeInput(e.target.value)},
            ['FAB','CUP','OFFICE','物流中心','其他'].map(t =>
              React.createElement('option', {key:t, value:t}, t)
            )
          )
        ),
        /* Buttons */
        React.createElement('div', {className:'field', style:{display:'flex', alignItems:'flex-end', gap:8}},
          React.createElement(Btn, {kind:'primary', icon:ICONS.zap, onClick:handleSave, disabled:saving},
            saving ? '儲存中...' : '儲存快照'),
          React.createElement(Btn, {kind:'ghost', onClick:() => setParseResult(null)}, '取消')
        )
      ),
      /* Preview items */
      parseResult.items && Object.keys(parseResult.items).length > 0 &&
        React.createElement('div', {className:'stack', style:{gap:6}},
          React.createElement('div', {className:'section-label', style:{margin:0}}, '13 項預覽'),
          KG_ITEMS.filter(name => parseResult.items[name]).map(name =>
            React.createElement('div', {key:name, className:'row-between', style:{padding:'4px 0', fontSize:12.5}},
              React.createElement('span', null, name),
              React.createElement('span', {className:'num'},
                '結算 ', formatTWD(parseResult.items[name].settlement || 0),
                React.createElement('span', {className:'muted', style:{marginLeft:8}},
                  '預算 ', formatTWD(parseResult.items[name].budget || 0)
                )
              )
            )
          )
        )
    ),

    /* ========== Project selector buttons ========== */
    projects.length > 0 && React.createElement('div', {className:'row', style:{gap:8, flexWrap:'wrap', marginBottom:16}},
      projects.map(dn =>
        React.createElement('button', {
          key: dn,
          className: 'btn btn-sm ' + (selectedDn === dn ? 'btn-soft' : 'btn-ghost'),
          onClick: () => setSelectedDn(dn)
        }, dn)
      )
    ),

    /* ========== Saved snapshot display ========== */
    latestSnap ? React.createElement(React.Fragment, null,

      /* --- Area info card (always visible, editable) --- */
      React.createElement(Card, {
        title: '面積與單位假設工程費',
        accent: 'var(--accent)',
        style: {marginBottom:16}
      },
        React.createElement('div', {style:{display:'flex', gap:24, alignItems:'flex-start', flexWrap:'wrap'}},

          /* Left: area display/edit */
          React.createElement('div', {style:{flex:'1 1 280px', minWidth:200}},
            !editingArea ?
              /* Display mode */
              React.createElement('div', {style:{display:'flex', alignItems:'center', gap:16, flexWrap:'wrap'}},
                React.createElement('div', null,
                  React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:2}}, '面積（坪）'),
                  React.createElement('div', {style:{fontSize:28, fontWeight:700, color:'var(--primary-600)', fontFamily:'var(--font-mono)'}},
                    latestSnap.area_ping ? latestSnap.area_ping.toLocaleString() : '—'
                  ),
                  latestSnap.area_ping > 0 && React.createElement('div', {className:'muted', style:{fontSize:11, fontFamily:'var(--font-mono)'}},
                    '≈ ', Math.round(latestSnap.area_ping / 0.3025).toLocaleString(), ' m²'
                  )
                ),
                React.createElement(Btn, {kind:'ghost', onClick: () => {
                  setEditAreaVal(latestSnap.area_ping || 0);
                  setEditingArea(true);
                }}, latestSnap.area_ping ? '修改面積' : '設定面積')
              )
            :
              /* Edit mode */
              React.createElement('div', null,
                React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:4}}, '輸入面積（坪）'),
                React.createElement('div', {style:{display:'flex', gap:8, alignItems:'center'}},
                  React.createElement('input', {className:'field-input num', type:'number', min:0, step:100,
                    value: editAreaVal, onChange: e => setEditAreaVal(+e.target.value),
                    style:{fontSize:18, fontWeight:600, width:160},
                    autoFocus: true
                  }),
                  React.createElement(Btn, {kind:'primary', disabled:savingArea,
                    onClick: () => handleUpdateArea(latestSnap)},
                    savingArea ? '儲存中...' : '確認'
                  ),
                  React.createElement(Btn, {kind:'ghost', onClick: () => setEditingArea(false)}, '取消')
                ),
                editAreaVal > 0 && React.createElement('div', {className:'muted', style:{fontSize:11, marginTop:4, fontFamily:'var(--font-mono)'}},
                  '≈ ', Math.round(editAreaVal / 0.3025).toLocaleString(), ' m²'
                )
              )
          ),

          /* Middle: unit cost per ping */
          React.createElement('div', {style:{flex:'0 0 auto', textAlign:'center', padding:'0 24px',
            borderLeft:'1px solid var(--border)', borderRight:'1px solid var(--border)'}},
            React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:2}}, '假設工程/坪（萬）'),
            React.createElement('div', {style:{fontSize:28, fontWeight:700, color:'var(--primary-600)', fontFamily:'var(--font-mono)'}},
              (() => {
                var uc = unitCostPing(latestSnap.total_settle, editingArea ? editAreaVal : latestSnap.area_ping);
                return uc !== null ? uc.toFixed(2) : '—';
              })()
            ),
            React.createElement('div', {className:'muted', style:{fontSize:11}}, '結算合計 / 面積')
          ),

          /* Right: unit cost per m2 */
          React.createElement('div', {style:{flex:'0 0 auto', textAlign:'center', paddingLeft:0}},
            React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:2}}, '假設工程/m²（元）'),
            React.createElement('div', {style:{fontSize:28, fontWeight:700, color:'var(--text)', fontFamily:'var(--font-mono)'}},
              (() => {
                var ucm = unitCostM2(latestSnap.total_settle, editingArea ? editAreaVal : latestSnap.area_ping);
                return ucm !== null ? Math.round(ucm).toLocaleString() : '—';
              })()
            ),
            React.createElement('div', {className:'muted', style:{fontSize:11}}, '換算平方公尺')
          )
        ),

        /* Warning if no area */
        !latestSnap.area_ping && !editingArea && React.createElement('div', {
          className: 'alert alert-info', style: {marginTop:12}
        },
          React.createElement('span', {className:'alert-dot'}),
          React.createElement('div', {className:'alert-body'},
            React.createElement('strong', null, '尚未設定面積'), ' — 請點擊「設定面積」以計算單位假設工程費'
          )
        )
      ),

      /* --- KPI cards --- */
      React.createElement('div', {className:'grid grid-4', style:{marginBottom:16}},
        React.createElement(KPI, {label:'假設工程結算', value:formatTWD(latestSnap.total_settle),
          sub: latestSnap.area_ping ? '面積 ' + latestSnap.area_ping.toLocaleString() + ' 坪' : '未設面積',
          color:'var(--primary-500)'}),
        React.createElement(KPI, {label:'單位假設工程費',
          value: latestSnap.area_ping ? ((latestSnap.total_settle / latestSnap.area_ping / 10000).toFixed(2) + ' 萬/坪') : '—',
          sub: latestSnap.area_ping ? '結算 / 面積' : '需設定面積',
          color:'var(--primary-500)'}),
        React.createElement(KPI, {label:'假設工程預算', value:formatTWD(latestSnap.total_budget),
          sub:'預算金額', color:'var(--good)', tone:'good'}),
        React.createElement(KPI, {label:'快照期數', value:snapshots.length,
          sub:'歷史記錄', color:'var(--muted)'})
      ),

      /* --- Project header --- */
      React.createElement('div', {className:'proj-header'},
        React.createElement('div', {style:{flex:1, zIndex:1}},
          React.createElement('h2', null, latestSnap.full_name || selectedDn),
          React.createElement('div', {className:'sub'},
            selectedDn, ' · 截止日 ', latestSnap.file_date || latestSnap.read_date, ' · 第 ', snapshots.length, ' 期'
          ),
          React.createElement('div', {className:'proj-tags'},
            latestSnap.project_type && React.createElement('span', {className:'proj-tag'}, latestSnap.project_type),
            latestSnap.conditions?.region && React.createElement('span', {className:'proj-tag'}, latestSnap.conditions.region)
          )
        ),
        React.createElement('div', {className:'row', style:{gap:0, zIndex:1}},
          React.createElement('div', {className:'mini-stat'},
            React.createElement('div', {className:'mini-stat-l'}, '結算'),
            React.createElement('div', {className:'mini-stat-v'}, formatTWD(latestSnap.total_settle))
          ),
          React.createElement('div', {className:'mini-stat'},
            React.createElement('div', {className:'mini-stat-l'}, '預算'),
            React.createElement('div', {className:'mini-stat-v'}, formatTWD(latestSnap.total_budget))
          ),
          latestSnap.area_ping > 0 && React.createElement('div', {className:'mini-stat'},
            React.createElement('div', {className:'mini-stat-l'}, '萬/坪'),
            React.createElement('div', {className:'mini-stat-v'}, (latestSnap.total_settle / latestSnap.area_ping / 10000).toFixed(2))
          )
        )
      ),

      /* --- Tabs --- */
      React.createElement('div', {style:{marginBottom:16}},
        React.createElement(Tabs, {tabs:[
          {key:'analysis', label:'分析表'},
          {key:'trend', label:'趨勢追蹤', count: snapshots.length},
        ], active:activeTab, onChange:setActiveTab})
      ),

      /* Analysis table */
      activeTab === 'analysis' && React.createElement(AnalysisTable, {
        items:latestSnap.items, prevItems:prevSnap?.items,
        totalBudget:latestSnap.total_budget, totalSettle:latestSnap.total_settle,
        areaPing: latestSnap.area_ping
      }),

      /* Trend */
      activeTab === 'trend' && snapshots.length > 1 && React.createElement(Card, {
        title:'結算趨勢', accent:'var(--primary-500)'
      },
        React.createElement(TrendChart, {
          data:snapshots.map(s => ({label:(s.file_date || s.read_date || '').slice(5), value:s.total_settle})),
          color:"var(--primary-500)", accentColor:"var(--accent)", h:320
        })
      )
    )
    :
    /* No snapshot selected */
    (projects.length > 0 && selectedDn ?
      React.createElement(EmptyState, {title:'此專案尚無快照', sub:'請匯入 KG 一覽表'})
    : !parseResult && React.createElement(EmptyState, {title:'尚無資料', sub:'點擊右上角「匯入假設工程」開始上傳'})
    )
  );
}

function AnalysisTable({ items, prevItems, totalBudget, totalSettle, areaPing }) {
  if (!items || Object.keys(items).length === 0) {
    return React.createElement(EmptyState, {title:'無項目資料', sub:'快照中未包含項目明細'});
  }

  var rows = KG_ITEMS.filter(function(name) { return items[name]; }).map(function(name) {
    var curr = items[name];
    var prev = prevItems ? prevItems[name] : null;
    var delta = prev ? curr.settlement - prev.settlement : 0;
    var pct = prev && prev.settlement ? (delta / prev.settlement) * 100 : 0;
    return { name: name, budget: curr.budget||0, settlement: curr.settlement||0,
      diff: (curr.budget||0) - (curr.settlement||0), delta: delta, pct: pct };
  });

  return React.createElement(Card, {
    title:'13 項假設工程明細', accent:'var(--primary-500)', className:'card-flush'
  },
    React.createElement('div', {className:'scroll-x'},
      React.createElement('table', {className:'table'},
        React.createElement('thead', null,
          React.createElement('tr', null,
            React.createElement('th', {style:{minWidth:110}}, '項目'),
            React.createElement('th', {className:'right'}, '預算'),
            React.createElement('th', {className:'right'}, '結算'),
            React.createElement('th', {className:'right'}, '差異'),
            areaPing > 0 && React.createElement('th', {className:'right'}, '萬/坪'),
            prevItems && React.createElement('th', {className:'right'}, '本期 Δ')
          )
        ),
        React.createElement('tbody', null,
          rows.map(function(r) {
            return React.createElement('tr', {key:r.name},
              React.createElement('td', {className:'col-name'},
                React.createElement('span', {className:'status-dot status-active', style:{marginRight:8}}), r.name
              ),
              React.createElement('td', {className:'num'}, formatTWD(r.budget)),
              React.createElement('td', {className:'num'}, formatTWD(r.settlement)),
              React.createElement('td', {className:'num ' + (r.diff >= 0 ? 'delta-up' : 'delta-down')},
                (r.diff >= 0 ? '+' : '') + formatTWD(Math.abs(r.diff))
              ),
              areaPing > 0 && React.createElement('td', {className:'num', style:{color:'var(--primary-600)', fontFamily:'var(--font-mono)'}},
                (r.settlement / areaPing / 10000).toFixed(2)
              ),
              prevItems && React.createElement('td', {className:'num ' + (r.delta >= 0 ? 'delta-up' : 'delta-down')},
                (r.pct >= 0 ? '+' : '') + r.pct.toFixed(1) + '%'
              )
            );
          }),
          React.createElement('tr', {style:{background:'var(--surface-2)'}},
            React.createElement('td', {style:{fontWeight:700, color:'var(--text)'}}, '合計'),
            React.createElement('td', {className:'num', style:{fontWeight:700, color:'var(--text)'}}, formatTWD(totalBudget)),
            React.createElement('td', {className:'num', style:{fontWeight:700, color:'var(--text)'}}, formatTWD(totalSettle)),
            React.createElement('td', {className:'num'}, '—'),
            areaPing > 0 && React.createElement('td', {className:'num', style:{fontWeight:700, color:'var(--primary-600)', fontFamily:'var(--font-mono)'}},
              (totalSettle / areaPing / 10000).toFixed(2)
            ),
            prevItems && React.createElement('td', null, '—')
          )
        )
      )
    )
  );
}

Object.assign(window, { PageAssumption });
