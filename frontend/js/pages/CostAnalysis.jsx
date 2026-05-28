// 造價分析 — 八大類下鑽、上傳分析、面積設定、Excel 下載
const { useState: useStateC, useEffect: useEffectC, useRef: useRefC } = React;

const BIG_GROUPS = [
  { id: '假設工程', name: '假設工程', color: '#1E40AF' },
  { id: '基礎工程', name: '基礎工程', color: '#2563EB' },
  { id: '結構工程', name: '結構工程', color: '#3B82F6' },
  { id: '裝修工程', name: '裝修工程', color: '#60A5FA' },
  { id: '設備工程', name: '設備工程', color: '#93C5FD' },
  { id: '景觀外構', name: '景觀外構', color: '#0EA5E9' },
  { id: '機電工程', name: '機電工程', color: '#38BDF8' },
  { id: '營造管理', name: '營造管理', color: '#7DD3FC' },
];

function PageCost({ setPage }) {
  const [projects, setProjects] = useStateC([]);
  const [selectedDn, setSelectedDn] = useStateC(null);
  const [snapshots, setSnapshots] = useStateC([]);
  const [analyzing, setAnalyzing] = useStateC(false);
  const [parseResult, setParseResult] = useStateC(null);
  const [areaInput, setAreaInput] = useStateC(0);
  const [typeInput, setTypeInput] = useStateC('其他');
  const [saving, setSaving] = useStateC(false);
  // For editing area on saved snapshots
  const [editingArea, setEditingArea] = useStateC(false);
  const [editAreaVal, setEditAreaVal] = useStateC(0);
  const [savingArea, setSavingArea] = useStateC(false);
  const fileRef = useRefC(null);

  useEffectC(() => {
    API.getProjects().then(data => {
      const names = (data?.projects || []).filter(p => p.cost_count > 0).map(p => p.display_name);
      setProjects(names);
      if (names.length > 0 && !selectedDn) setSelectedDn(names[0]);
    }).catch(() => {});
  }, []);

  useEffectC(() => {
    if (!selectedDn) return;
    setEditingArea(false);
    API.getCost(selectedDn).then(data => {
      setSnapshots(data?.snapshots || []);
    }).catch(() => setSnapshots([]));
  }, [selectedDn]);

  async function handleUpload(files) {
    setAnalyzing(true);
    setParseResult(null);
    try {
      const result = await API.analyzeCost(files);
      const items = result?.results || [];
      const first = items.find(r => !r.error);
      if (!first) {
        const errMsg = items[0]?.error || '無法分析檔案';
        alert('分析失敗：' + errMsg);
        return;
      }
      setParseResult(first);
      setTypeInput(first.detected_type || '其他');
      // Try to get saved area from areas API
      try {
        const areas = await API.getAreas();
        const savedArea = areas?.[first.display_name] || 0;
        setAreaInput(savedArea);
      } catch(e) { setAreaInput(0); }
    } catch (e) {
      alert('分析失敗：' + e.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleSave() {
    if (!parseResult) return;
    setSaving(true);
    try {
      const payload = {
        display_name: parseResult.display_name,
        project_full: '',
        area_ping: areaInput,
        area_m2: areaInput > 0 ? Math.round(areaInput / 0.3025) : 0,
        total_settle: parseResult.total_settle || 0,
        big_groups: parseResult.big_groups || {},
        items: parseResult.items || [],
        unassigned_count: parseResult.unassigned_count || 0,
        source_filename: parseResult.filename || '',
        excel_filename: parseResult.excel_filename || '',
        file_date: parseResult.file_date || '',
        project_type: typeInput,
        conditions: {},
      };
      await API.saveCost(payload);
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
      const names = (data?.projects || []).filter(p => p.cost_count > 0).map(p => p.display_name);
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
      await API.updateCostArea(snap.id, editAreaVal, selectedDn);
      // Reload snapshots
      const data = await API.getCost(selectedDn);
      setSnapshots(data?.snapshots || []);
      setEditingArea(false);
    } catch (e) {
      alert('面積更新失敗：' + e.message);
    } finally {
      setSavingArea(false);
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

  const latestSnap = snapshots[snapshots.length - 1];

  // Compute unit cost helper
  function unitCostPing(total, area) {
    if (!area || area <= 0) return null;
    return total / area / 10000; // 萬/坪
  }
  function unitCostM2(total, area) {
    if (!area || area <= 0) return null;
    var m2 = area / 0.3025;
    return total / m2;            // 元/m²
  }

  return (
    React.createElement(React.Fragment, null,
      React.createElement(TopBar, {
        title: "造價分析",
        breadcrumb: "總覽 / 造價分析",
        subtitle: "上傳 KG 一覽表．設定面積．產出八大類造價分析",
        actions: React.createElement(React.Fragment, null,
          React.createElement(Btn, {kind:"primary", icon:ICONS.upload, onClick:() => fileRef.current?.click()}, "上傳造價 Excel"),
          React.createElement('input', {ref:fileRef, type:'file', accept:'.xlsx,.xls', multiple:true,
            style:{display:'none'},
            onChange: e => { if (e.target.files.length > 0) handleUpload(Array.from(e.target.files)); }
          })
        )
      }),

      /* Analyzing indicator */
      analyzing && React.createElement('div', {className:'alert alert-info', style:{marginBottom:16}},
        React.createElement('span', {className:'alert-dot'}),
        React.createElement('div', {className:'alert-body'},
          React.createElement('strong', null, '分析中...'), ' 正在解析上傳的 Excel'
        )
      ),

      /* ========== Upload result + area input panel ========== */
      parseResult && !analyzing && React.createElement(Card, {
        title: '分析結果 — 設定面積後儲存',
        accent: 'var(--accent)',
        style: {marginBottom:16}
      },
        React.createElement('div', {className:'alert alert-success', style:{marginBottom:16}},
          React.createElement('span', {className:'alert-dot'}),
          React.createElement('div', {className:'alert-body'},
            React.createElement('strong', null, parseResult.display_name),
            ' · 截止日 ', parseResult.file_date, ' · 結算 ', formatTWD(parseResult.total_settle)
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
                '單位造價 ', (parseResult.total_settle / areaInput / 10000).toFixed(2), ' 萬/坪'
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
        /* Preview big groups */
        parseResult.big_groups && Object.keys(parseResult.big_groups).length > 0 &&
          React.createElement('div', {className:'stack', style:{gap:6}},
            React.createElement('div', {className:'section-label', style:{margin:0}}, '八大類預覽'),
            BIG_GROUPS.filter(g => parseResult.big_groups[g.id]).map(g =>
              React.createElement('div', {key:g.id, className:'row-between', style:{padding:'4px 0', fontSize:12.5}},
                React.createElement('span', {style:{display:'inline-flex', alignItems:'center', gap:8}},
                  React.createElement('span', {className:'legend-dot', style:{background:g.color}}), g.name
                ),
                React.createElement('span', {className:'num'}, formatTWD(parseResult.big_groups[g.id]))
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
          title: '面積與單位造價',
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
              React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:2}}, '單位造價（萬/坪）'),
              React.createElement('div', {style:{fontSize:28, fontWeight:700, color:'var(--primary-600)', fontFamily:'var(--font-mono)'}},
                (() => {
                  var uc = unitCostPing(latestSnap.total_settle, editingArea ? editAreaVal : latestSnap.area_ping);
                  return uc !== null ? uc.toFixed(2) : '—';
                })()
              ),
              React.createElement('div', {className:'muted', style:{fontSize:11}}, '含八大類合計')
            ),

            /* Right: unit cost per m2 */
            React.createElement('div', {style:{flex:'0 0 auto', textAlign:'center', paddingLeft:0}},
              React.createElement('div', {className:'muted', style:{fontSize:11, marginBottom:2}}, '單位造價（元/m²）'),
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
              React.createElement('strong', null, '尚未設定面積'), ' — 請點擊「設定面積」以計算單位造價'
            )
          )
        ),

        /* --- KPI cards --- */
        React.createElement('div', {className:'grid grid-4', style:{marginBottom:16}},
          React.createElement(KPI, {label:'總造價', value:formatTWD(latestSnap.total_settle),
            sub: latestSnap.area_ping ? '面積 ' + latestSnap.area_ping.toLocaleString() + ' 坪' : '未設面積',
            color:'var(--primary-500)'}),
          React.createElement(KPI, {label:'單位造價',
            value: latestSnap.area_ping ? ((latestSnap.total_settle / latestSnap.area_ping / 10000).toFixed(2) + ' 萬/坪') : '—',
            sub: latestSnap.area_ping ? '含八大類合計' : '需設定面積',
            color:'var(--primary-500)'}),
          React.createElement(KPI, {label:'八大類',
            value: Object.keys(latestSnap.big_groups || {}).length,
            sub:'已分類', color:'var(--good)', tone:'good'}),
          React.createElement(KPI, {label:'快照期數', value:snapshots.length,
            sub:'歷史記錄', color:'var(--muted)'})
        ),

        /* --- Charts --- */
        React.createElement('div', {className:'grid grid-2', style:{marginBottom:16}},
          React.createElement(Card, {title:'造價組成', accent:'var(--primary-500)'},
            latestSnap.big_groups && Object.keys(latestSnap.big_groups).length > 0 ?
              React.createElement(React.Fragment, null,
                React.createElement('div', {style:{display:'flex', justifyContent:'center'}},
                  React.createElement(Donut, {
                    data: BIG_GROUPS.filter(g => latestSnap.big_groups[g.id])
                      .map(g => ({label:g.name, value:latestSnap.big_groups[g.id], color:g.color})),
                    size: 220
                  })
                ),
                React.createElement('div', {className:'stack', style:{marginTop:16, gap:6}},
                  BIG_GROUPS.filter(g => latestSnap.big_groups[g.id]).map(g =>
                    React.createElement('div', {key:g.id, className:'row-between', style:{padding:'4px 0', fontSize:12.5}},
                      React.createElement('span', {style:{display:'inline-flex', alignItems:'center', gap:8}},
                        React.createElement('span', {className:'legend-dot', style:{background:g.color}}), g.name
                      ),
                      React.createElement('span', null,
                        React.createElement('span', {className:'num'}, formatTWD(latestSnap.big_groups[g.id])),
                        latestSnap.area_ping > 0 && React.createElement('span', {className:'muted', style:{marginLeft:8, fontSize:11}},
                          (latestSnap.big_groups[g.id] / latestSnap.area_ping / 10000).toFixed(2), ' 萬/坪'
                        )
                      )
                    )
                  )
                )
              )
            :
              React.createElement(EmptyState, {title:'無八大類資料', sub:'此快照未包含八大類分類'})
          ),

          React.createElement(Card, {title:'八大類成本柱狀圖', accent:'var(--accent)'},
            latestSnap.big_groups && Object.keys(latestSnap.big_groups).length > 0 ?
              React.createElement(BarChart, {
                h: 360, color:'var(--primary-500)', accentColor:'var(--accent)',
                data: BIG_GROUPS.filter(g => latestSnap.big_groups[g.id])
                  .map(g => ({key:g.id, label:g.name, value:latestSnap.big_groups[g.id], color:g.color}))
              })
            :
              React.createElement(EmptyState, {title:'無資料', sub:'上傳 Excel 以生成八大類分析'})
          )
        ),

        /* --- Download button --- */
        latestSnap.id && React.createElement('div', {style:{marginTop:12}},
          React.createElement(Btn, {kind:'ghost', icon:ICONS.download, onClick: () => handleDownload(latestSnap.id)},
            '下載最新 Excel'
          )
        )

      ) : !parseResult && React.createElement(EmptyState, {
        title: projects.length > 0 ? '此專案尚無造價快照' : '尚無造價分析資料',
        sub: '上傳造價 Excel 以開始分析',
        action: React.createElement(Btn, {kind:'primary', icon:ICONS.upload, onClick: () => fileRef.current?.click()},
          '上傳造價 Excel'
        )
      })
    )
  );
}

Object.assign(window, { PageCost });
