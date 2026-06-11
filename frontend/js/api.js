// API 連接層 — 所有後端呼叫都透過此模組
// FastAPI 在同一個 origin 提供服務，路徑為 /api/*
window.API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  },

  async post(path, body) {
    const r = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  },

  async upload(path, files) {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    const r = await fetch(path, { method: 'POST', body: fd });
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  },

  async put(path, body) {
    const r = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  },

  async del(path) {
    const r = await fetch(path, { method: 'DELETE' });
    if (!r.ok) throw new Error(r.status + ' ' + r.statusText);
    return r.json();
  },

  // === Endpoints ===
  getProjects()              { return this.get('/api/projects'); },
  getTypeCounts()            { return this.get('/api/type-counts'); },
  getAssumption(dn)          { return this.get('/api/assumption/' + encodeURIComponent(dn)); },
  getCost(dn)                { return this.get('/api/cost/' + encodeURIComponent(dn)); },
  getPrediction(type, area, opts = {}) {
    const p = new URLSearchParams({ project_type: type, area_ping: area });
    if (opts.structType)    p.set('struct_type', opts.structType);
    if (opts.contractMode)  p.set('contract_mode', opts.contractMode);
    if (opts.withMaterial)  p.set('with_material', opts.withMaterial);
    if (opts.escalate === false) p.set('escalate', 'false');
    if (opts.rebarPrice)    p.set('rebar_price', opts.rebarPrice);
    if (opts.concretePrice) p.set('concrete_price', opts.concretePrice);
    if (opts.labor)    p.set('labor', opts.labor);
    return this.get('/api/prediction?' + p.toString());
  },
  getCostIndex()             { return this.get('/api/cost-index'); },
  saveCostIndex(index)       { return this.put('/api/cost-index', { index }); },
  getMaterialPrices()        { return this.get('/api/material-prices'); },
  saveMaterialPrices(prices) { return this.put('/api/material-prices', { prices }); },
  updateConditions(table, sid, conditions) {
    return this.put('/api/snapshot/' + table + '/' + sid + '/conditions', { conditions });
  },
  getHistory(table)          { return this.get('/api/history?table=' + table); },
  getAreas()                 { return this.get('/api/areas'); },
  saveAreas(areas)           { return this.put('/api/areas', { areas }); },

  parseKG(files)             { return this.upload('/api/parse-kg', files); },
  saveAssumption(data)       { return this.post('/api/assumption/save', data); },
  analyzeCost(files)         { return this.upload('/api/cost/analyze', files); },
  saveCost(data)             { return this.post('/api/cost/save', data); },
  updateCostArea(sid, areaPing, dn) { return this.put('/api/cost/' + sid + '/area', { area_ping: areaPing, display_name: dn }); },
  updateAssumptionArea(sid, areaPing, dn) { return this.put('/api/assumption/' + sid + '/area', { area_ping: areaPing, display_name: dn }); },

  deleteSnapshot(table, sid) { return this.del('/api/snapshot/' + table + '/' + sid); },
  getHealth()               { return this.get('/api/health'); },
  createBackup()            { return this.post('/api/backup', {}); },

  batchAnalyze(files)       { return this.upload('/api/batch-analyze', files); },
  batchSave(items)          { return this.post('/api/batch-save', { items }); },

  async downloadExcel(sid) {
    const r = await fetch('/api/cost/excel/' + sid);
    if (!r.ok) throw new Error(r.status + '');
    const blob = await r.blob();
    const cd = r.headers.get('content-disposition');
    const filename = cd ? cd.split('filename=')[1] : 'export.xlsx';
    return { blob, filename };
  },
};
