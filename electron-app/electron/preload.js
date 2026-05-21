// Preload — 安全暴露 API 給 renderer
const { contextBridge } = require('electron');

const API_BASE = 'http://127.0.0.1:8000';

contextBridge.exposeInMainWorld('api', {
  baseUrl: API_BASE,

  // 通用 fetch wrapper
  async get(path) {
    const r = await fetch(`${API_BASE}${path}`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  },

  async post(path, body) {
    const r = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  },

  async upload(path, files) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    const r = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: formData,
    });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  },

  async del(path) {
    const r = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  },

  // 下載 Excel blob
  async downloadExcel(sid) {
    const r = await fetch(`${API_BASE}/api/cost/excel/${sid}`);
    if (!r.ok) throw new Error(`${r.status}`);
    return {
      blob: await r.blob(),
      filename: r.headers.get('content-disposition')?.split('filename=')[1] || 'export.xlsx',
    };
  },
});
