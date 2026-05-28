// 批次匯入 — 多檔上傳、自動偵測假設工程/造價、面積帶入、一鍵儲存
const { useState: useStateBU, useEffect: useEffectBU, useRef: useRefBU } = React;

function PageBatch({ setPage }) {
  var _s = useStateBU, _r = useRefBU;
  var [results, setResults] = _s([]);
  var [uploading, setUploading] = _s(false);
  var [saving, setSaving] = _s(false);
  var [done, setDone] = _s(false);
  var [saveResult, setSaveResult] = _s(null);
  var [checked, setChecked] = _s({});
  var [areas, setAreas] = _s({});
  var [types, setTypes] = _s({});
  var [dragOver, setDragOver] = _s(false);
  var [fileCount, setFileCount] = _s(0);
  var fileRef = _r(null);

  // Auto-start if files were passed from Home page
  useEffectBU(function() {
    if (window.__batchFiles) {
      var files = window.__batchFiles;
      window.__batchFiles = null;
      handleFiles(files);
    }
  }, []);

  async function handleFiles(fileList) {
    setUploading(true);
    setResults([]);
    setDone(false);
    setSaveResult(null);
    setFileCount(fileList.length);
    try {
      var data = await API.batchAnalyze(fileList);
      var items = data?.results || [];
      setResults(items);
      var ch = {}, ar = {}, ty = {};
      items.forEach(function(r, i) {
        if (!r.error) {
          ch[i] = true;
          ar[i] = r.area_ping || 0;
          ty[i] = r.detected_type || r.project_type || '其他';
        }
      });
      setChecked(ch);
      setAreas(ar);
      setTypes(ty);
    } catch (e) {
      alert('解析失敗：' + e.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      var items = results
        .map(function(r, i) {
          if (!checked[i] || r.error) return null;
          return Object.assign({}, r, {
            area_ping: areas[i] || 0,
            project_type: types[i] || '其他'
          });
        })
        .filter(Boolean);
      var data = await API.batchSave(items);
      setSaveResult(data);
      setDone(true);
    } catch (e) {
      alert('儲存失敗：' + e.message);
    } finally {
      setSaving(false);
    }
  }

  function toggleAll(val) {
    var ch = {};
    results.forEach(function(r, i) { if (!r.error) ch[i] = val; });
    setChecked(ch);
  }

  function resetAll() {
    setResults([]); setChecked({}); setAreas({}); setTypes({});
    setDone(false); setSaveResult(null);
  }

  // Stats
  var validResults = results.filter(function(r) { return !r.error; });
  var checkedCount = Object.keys(checked).filter(function(k) { return checked[k]; }).length;
  var assumptionItems = results.filter(function(r, i) { return !r.error && checked[i] && r.analysis_type === 'assumption'; });
  var costItems = results.filter(function(r, i) { return !r.error && checked[i] && r.analysis_type === 'cost'; });
  var areaFilled = results.filter(function(r, i) { return !r.error && checked[i] && (areas[i] || 0) > 0; });
  var areaEmpty = results.filter(function(r, i) { return !r.error && checked[i] && !(areas[i] > 0); });
  var errorItems = results.filter(function(r) { return r.error; });

  return React.createElement(React.Fragment, null,

    React.createElement(TopBar, {
      title: '批次匯入',
      breadcrumb: '總覽 / 批次匯入',
      subtitle: '拖放多個 Excel 檔案，系統自動偵測假設工程 / 造價分析並帶入面積'
    }),

    /* ======= Success state ======= */
    done && saveResult && React.createElement('div', {style:{textAlign:'center', padding:'48px 20px'}},
      React.createElement('div', {style:{
        width:64, height:64, borderRadius:'50%', background:'var(--good-soft)',
        display:'flex', alignItems:'center', justifyContent:'center',
        margin:'0 auto 16px', fontSize:28, color:'var(--good)'
      }}, React.createElement('span', {dangerouslySetInnerHTML:{__html: ICONS.check || '&#10003;'}})),
      React.createElement('h2', {style:{marginBottom:8}}, '批次匯入完成'),
      React.createElement('div', {style:{fontSize:14, color:'var(--muted)'}},
        '成功儲存 ' + saveResult.total_saved + ' 筆',
        saveResult.total_errors > 0 ? ('，' + saveResult.total_errors + ' 筆失敗') : ''
      ),

      /* Saved details */
      saveResult.saved && saveResult.saved.length > 0 &&
        React.createElement('div', {className:'grid grid-2', style:{
          marginTop:24, maxWidth:600, marginLeft:'auto', marginRight:'auto', textAlign:'left'
        }},
          React.createElement(Card, {title:'假設工程', accent:'var(--primary-500)'},
            React.createElement('div', {className:'stack', style:{gap:4}},
              saveResult.saved.filter(function(s){return s.analysis_type==='assumption';}).map(function(s, i) {
                return React.createElement('div', {key:i, style:{fontSize:12.5, padding:'4px 0'}},
                  React.createElement('span', {className:'status-dot status-active', style:{marginRight:6}}),
                  s.display_name
                );
              }),
              saveResult.saved.filter(function(s){return s.analysis_type==='assumption';}).length === 0 &&
                React.createElement('div', {className:'muted', style:{fontSize:12}}, '無')
            )
          ),
          React.createElement(Card, {title:'造價分析', accent:'var(--accent)'},
            React.createElement('div', {className:'stack', style:{gap:4}},
              saveResult.saved.filter(function(s){return s.analysis_type==='cost';}).map(function(s, i) {
                return React.createElement('div', {key:i, style:{fontSize:12.5, padding:'4px 0'}},
                  React.createElement('span', {className:'status-dot status-active', style:{marginRight:6}}),
                  s.display_name
                );
              }),
              saveResult.saved.filter(function(s){return s.analysis_type==='cost';}).length === 0 &&
                React.createElement('div', {className:'muted', style:{fontSize:12}}, '無')
            )
          )
        ),

      /* Errors */
      saveResult.errors && saveResult.errors.length > 0 &&
        React.createElement('div', {style:{marginTop:16, maxWidth:600, marginLeft:'auto', marginRight:'auto', textAlign:'left'}},
          saveResult.errors.map(function(e, i) {
            return React.createElement('div', {key:i, className:'alert alert-warning', style:{marginBottom:8}},
              React.createElement('span', {className:'alert-dot'}),
              React.createElement('div', {className:'alert-body'},
                React.createElement('strong', null, e.display_name), ' — ', e.error
              )
            );
          })
        ),

      React.createElement('div', {style:{marginTop:24, display:'flex', gap:12, justifyContent:'center'}},
        React.createElement(Btn, {kind:'primary', onClick:function(){ setPage('home'); }}, '返回首頁'),
        React.createElement(Btn, {kind:'ghost', onClick:resetAll}, '繼續匯入')
      )
    ),

    /* ======= Drop zone (initial state) ======= */
    !done && results.length === 0 && !uploading &&
      React.createElement('div', {
        className: 'batch-drop-zone' + (dragOver ? ' batch-drop-active' : ''),
        onDragOver: function(e) { e.preventDefault(); setDragOver(true); },
        onDragLeave: function() { setDragOver(false); },
        onDrop: function(e) {
          e.preventDefault(); setDragOver(false);
          var files = Array.from(e.dataTransfer.files).filter(function(f) { return /\.xlsx?$/i.test(f.name); });
          if (files.length > 0) handleFiles(files);
        },
        onClick: function() { fileRef.current && fileRef.current.click(); }
      },
        React.createElement('div', {className:'batch-drop-icon', dangerouslySetInnerHTML:{__html: ICONS.upload}}),
        React.createElement('h3', {style:{margin:'16px 0 8px', color:'var(--text)'}}, '拖放 Excel 檔案至此，或點擊選取'),
        React.createElement('p', {style:{margin:0, fontSize:13, color:'var(--muted)', maxWidth:420}},
          '支援 .xlsx / .xls · 可同時選取多個檔案'
        ),
        React.createElement('p', {style:{margin:'12px 0 0', fontSize:12, color:'var(--primary-500)', fontWeight:600}},
          '系統會自動偵測每個檔案的類型（假設工程 / 造價分析），並帶入已儲存的面積'
        ),
        React.createElement('input', {
          ref: fileRef, type: 'file', accept: '.xlsx,.xls', multiple: true,
          style: {display:'none'},
          onChange: function(e) {
            if (e.target.files.length > 0) handleFiles(Array.from(e.target.files));
            e.target.value = '';
          }
        })
      ),

    /* ======= Uploading indicator ======= */
    uploading && React.createElement('div', {style:{textAlign:'center', padding:'64px 20px'}},
      React.createElement('div', {style:{
        width:48, height:48, border:'3px solid var(--border)',
        borderTopColor:'var(--primary-500)', borderRadius:'50%',
        animation:'spin 1s linear infinite', margin:'0 auto 16px'
      }}),
      React.createElement('h4', {style:{color:'var(--text)', marginBottom:4}}, '解析中...'),
      React.createElement('p', {className:'muted', style:{fontSize:13}},
        '正在分析 ' + fileCount + ' 個檔案，自動偵測假設工程與造價分析'
      )
    ),

    /* ======= Results table ======= */
    !done && results.length > 0 && !uploading && React.createElement(React.Fragment, null,

      /* KPI summary */
      React.createElement('div', {className:'grid grid-4', style:{marginBottom:16}},
        React.createElement(KPI, {label:'假設工程', value:assumptionItems.length + ' 筆',
          sub:'自動偵測', color:'var(--primary-500)'}),
        React.createElement(KPI, {label:'造價分析', value:costItems.length + ' 筆',
          sub:'自動偵測', color:'var(--accent)'}),
        React.createElement(KPI, {label:'已配面積', value:areaFilled.length + ' 筆',
          sub:'從面積紀錄帶入', color:'var(--good)', tone:'good'}),
        React.createElement(KPI, {label: areaEmpty.length > 0 ? '未配面積' : '來源檔案',
          value: areaEmpty.length > 0 ? areaEmpty.length + ' 筆' : fileCount + ' 個',
          sub: areaEmpty.length > 0 ? '請手動填入' : '全部已配面積',
          color: areaEmpty.length > 0 ? 'var(--warn)' : 'var(--muted)'})
      ),

      /* Area missing warning */
      areaEmpty.length > 0 &&
        React.createElement('div', {className:'alert alert-warning', style:{marginBottom:16}},
          React.createElement('span', {className:'alert-dot'}),
          React.createElement('div', {className:'alert-body'},
            React.createElement('strong', null, areaEmpty.length + ' 筆尚未設定面積'),
            ' — 黃底列表示未配面積，可在面積欄直接輸入。儲存後面積會自動記錄，下次上傳相同專案時自動帶入。'
          )
        ),

      /* Action bar */
      React.createElement('div', {className:'row-between', style:{marginBottom:16, flexWrap:'wrap', gap:12}},
        React.createElement('div', {className:'row', style:{gap:8}},
          React.createElement(Btn, {kind:'primary', icon:ICONS.zap, onClick:handleSave,
            disabled:saving || checkedCount === 0},
            saving ? '儲存中...' : '全部儲存 ' + checkedCount + ' 筆'
          ),
          React.createElement(Btn, {kind:'ghost', onClick:resetAll}, '清除重選')
        ),
        React.createElement(Btn, {kind:'ghost', icon:ICONS.upload, onClick:function() {
          fileRef.current && fileRef.current.click();
        }}, '追加檔案')
      ),

      /* Hidden file input for "追加檔案" */
      React.createElement('input', {
        ref: fileRef, type: 'file', accept: '.xlsx,.xls', multiple: true,
        style: {display:'none'},
        onChange: function(e) {
          if (e.target.files.length > 0) handleFiles(Array.from(e.target.files));
          e.target.value = '';
        }
      }),

      /* Error rows */
      errorItems.length > 0 &&
        React.createElement('div', {style:{marginBottom:16}},
          errorItems.map(function(r, i) {
            return React.createElement('div', {key:'err-'+i, className:'alert alert-warning', style:{marginBottom:8}},
              React.createElement('span', {className:'alert-dot'}),
              React.createElement('div', {className:'alert-body'},
                React.createElement('strong', null, r.filename), ' — ', r.error
              )
            );
          })
        ),

      /* Main table */
      React.createElement(Card, {title:'解析結果 — 確認面積與類型後儲存', accent:'var(--primary-500)', className:'card-flush'},
        React.createElement('div', {className:'table-scroll', style:{maxHeight:'unset'}},
          React.createElement('table', {className:'table'},
            React.createElement('thead', null,
              React.createElement('tr', null,
                React.createElement('th', {style:{width:40}},
                  React.createElement('input', {type:'checkbox',
                    checked: checkedCount === validResults.length && validResults.length > 0,
                    onChange: function(e) { toggleAll(e.target.checked); }
                  })
                ),
                React.createElement('th', null, '專案名稱'),
                React.createElement('th', {style:{width:90}}, '分析類別'),
                React.createElement('th', {style:{width:90}}, '類型'),
                React.createElement('th', {style:{width:100}}, '截止日'),
                React.createElement('th', {className:'right', style:{width:120}}, '結算'),
                React.createElement('th', {style:{width:130}}, '面積（坪）'),
                React.createElement('th', {className:'right', style:{width:80}}, '萬/坪')
              )
            ),
            React.createElement('tbody', null,
              validResults.length === 0 ?
                React.createElement('tr', null,
                  React.createElement('td', {colSpan:8, style:{textAlign:'center', padding:24, color:'var(--muted)'}},
                    '沒有可用的解析結果')
                )
              :
              results.map(function(r, i) {
                if (r.error) return null;
                var area = areas[i] || 0;
                var settle = r.total_settle || 0;
                var perPing = (area > 0 && settle > 0) ? (settle / area / 10000).toFixed(2) : '—';
                var isAssumption = r.analysis_type === 'assumption';
                var noArea = !(area > 0);

                return React.createElement('tr', {
                  key: i,
                  style: noArea ? {background:'var(--warn-bg, #fff8f0)'} : undefined
                },
                  React.createElement('td', null,
                    React.createElement('input', {type:'checkbox', checked:!!checked[i],
                      onChange:function(e) {
                        var c = Object.assign({}, checked);
                        c[i] = e.target.checked;
                        setChecked(c);
                      }
                    })
                  ),
                  React.createElement('td', {className:'col-name'},
                    React.createElement('span', {
                      className:'status-dot ' + (noArea ? 'status-warning' : 'status-active'),
                      style:{marginRight:6}
                    }),
                    r.display_name,
                    noArea && React.createElement('span', {style:{
                      marginLeft:6, fontSize:10, color:'var(--warn)', fontWeight:600
                    }}, '無面積')
                  ),
                  React.createElement('td', null,
                    React.createElement(Pill, {tone: isAssumption ? 'default' : 'muted'},
                      isAssumption ? '假設工程' : '造價分析'
                    )
                  ),
                  React.createElement('td', null,
                    React.createElement('select', {
                      className:'field-input',
                      value: types[i] || '其他',
                      onChange: function(e) {
                        var t = Object.assign({}, types);
                        t[i] = e.target.value;
                        setTypes(t);
                      },
                      style:{padding:'4px 8px', fontSize:12, width:'100%'}
                    },
                      ['FAB','CUP','OFFICE','物流中心','其他'].map(function(t) {
                        return React.createElement('option', {key:t, value:t}, t);
                      })
                    )
                  ),
                  React.createElement('td', {className:'mono', style:{fontSize:12, color:'var(--muted)'}},
                    r.file_date || '—'
                  ),
                  React.createElement('td', {className:'num'}, formatTWD(settle)),
                  React.createElement('td', null,
                    React.createElement('input', {
                      type:'number', className:'field-input num',
                      min:0, step:100,
                      value: area,
                      onChange: function(e) {
                        var a = Object.assign({}, areas);
                        a[i] = +e.target.value;
                        setAreas(a);
                      },
                      style:{padding:'4px 8px', fontSize:12, width:'100%'}
                    })
                  ),
                  React.createElement('td', {className:'num', style:{
                    fontFamily:'var(--font-mono)', color:'var(--primary-600)'
                  }}, perPing)
                );
              })
            )
          )
        )
      ),

      /* Bottom save bar */
      checkedCount > 0 &&
        React.createElement('div', {style:{
          marginTop:16, padding:'12px 16px', background:'var(--primary-50)',
          borderRadius:'var(--radius)', display:'flex', justifyContent:'space-between',
          alignItems:'center', flexWrap:'wrap', gap:12
        }},
          React.createElement('div', {style:{fontSize:13, color:'var(--primary-700)'}},
            '已選取 ',
            React.createElement('strong', null, checkedCount),
            ' 筆（假設工程 ',
            React.createElement('strong', null, assumptionItems.length),
            ' + 造價 ',
            React.createElement('strong', null, costItems.length),
            '）'
          ),
          React.createElement(Btn, {kind:'primary', icon:ICONS.zap, onClick:handleSave,
            disabled:saving},
            saving ? '儲存中...' : '確認儲存'
          )
        )
    )
  );
}

Object.assign(window, { PageBatch });
