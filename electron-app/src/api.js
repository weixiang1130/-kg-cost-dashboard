/**
 * API 連接層 — 統一封裝所有後端呼叫
 * 在 Electron 中透過 preload 暴露的 window.api
 * 在瀏覽器開發中直接 fetch（Vite proxy 轉發到 :8000）
 */

const BASE = window.api?.baseUrl || '/api';

async function get(path) {
  if (window.api) return window.api.get(path);
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function post(path, body) {
  if (window.api) return window.api.post(path, body);
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function upload(path, files) {
  if (window.api) return window.api.upload(path, files);
  const formData = new FormData();
  for (const f of files) formData.append('files', f);
  const r = await fetch(`${BASE}${path}`, { method: 'POST', body: formData });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function del(path) {
  if (window.api) return window.api.del(path);
  const r = await fetch(`${BASE}${path}`, { method: 'DELETE' });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ── 具體 API 函式 ──

export const api = {
  // 專案總覽
  getProjects: () => get('/api/projects'),
  getTypeCounts: () => get('/api/type-counts'),

  // 假設工程
  getAssumption: (dn) => get(`/api/assumption/${encodeURIComponent(dn)}`),
  saveAssumption: (data) => post('/api/assumption/save', data),
  parseKG: (files) => upload('/api/parse-kg', files),

  // 造價分析
  getCost: (dn) => get(`/api/cost/${encodeURIComponent(dn)}`),
  analyzeCost: (files) => upload('/api/cost/analyze', files),

  // 投標預估
  getPrediction: (projectType, areaPing) =>
    get(`/api/prediction?project_type=${encodeURIComponent(projectType)}&area_ping=${areaPing}`),

  // 歷史記錄
  getHistory: (table) => get(`/api/history?table=${table}`),
  deleteSnapshot: (table, sid) => del(`/api/snapshot/${table}/${sid}`),

  // 面積
  getAreas: () => get('/api/areas'),
  updateAreas: (areas) => post('/api/areas', { areas }),

  // Excel 下載
  downloadExcel: async (sid) => {
    if (window.api) return window.api.downloadExcel(sid);
    const r = await fetch(`/api/cost/excel/${sid}`);
    if (!r.ok) throw new Error(`${r.status}`);
    const blob = await r.blob();
    const filename = r.headers.get('content-disposition')?.split('filename=')[1] || 'export.xlsx';
    return { blob, filename };
  },
};

export default api;
