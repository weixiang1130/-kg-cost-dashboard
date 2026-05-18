#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成本管理自動化監測系統 — Streamlit 儀表板
讀取 KG 一覽表 → 分析假設工程/造價 → 追蹤歷史快照
"""
import os, json, re, warnings, io, zipfile, importlib, importlib.util, sys, sqlite3
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lxml import etree
warnings.filterwarnings('ignore')

DATA_DIR = Path("./kg_data"); DATA_DIR.mkdir(exist_ok=True)
DB_FILE = Path("./kg_history.db")
AREA_FILE = Path("./kg_areas.json")
LOGO_FILE = Path("./logo.png")
M2_PER_PING = 3.30579
PING_PER_M2 = 0.3025
ORDER = ['租工','打石工','技術工','零星建材','雜項工程','機具租金',
         '安衛零星','雜支一','雜支二','水費','電費','電話費','人員薪資']
PROJECT_TYPES = ['FAB', 'CUP', 'OFFICE', '物流中心', '其他']
REGIONS = ['竹科', '中科', '南科', '其他']
STRUCT_TYPES = ['RC', 'SC', 'SRC', '其他']
CONTRACT_MODES = ['', '點工', '包工', '連工帶料']

def detect_project_type(name):
    s = str(name).upper()
    if 'FAB' in s: return 'FAB'
    if 'CUP' in s: return 'CUP'
    if 'OFFICE' in s: return 'OFFICE'
    if '物流' in str(name): return '物流中心'
    return '其他'

def detect_fab_code(name):
    """從專案名偵測廠區代號，如 AP7P1、F22P5、AP6B 等"""
    import re
    s = str(name).upper()
    m = re.search(r'(AP\d+P?\d*|F\d+P?\d*)', s)
    return m.group(1) if m else ''

def detect_region(name):
    """從專案名猜測地區"""
    s = str(name)
    if '南科' in s: return '南科'
    if '中科' in s: return '中科'
    if '竹科' in s or '寶山' in s or '新竹' in s: return '竹科'
    return ''

def default_conditions():
    """回傳空白的條件字典"""
    return {
        'fab_code': '', 'region': '', 'struct_type': '',
        'floors': 0, 'duration_months': 0,
        'contract_mode': '', 'with_material': '', 'with_equipment': '',
        'rebar_price': 0, 'concrete_price': 0, 'formwork_price': 0,
        'price_index': 0, 'note': '',
    }

def render_conditions_input(dn, key_prefix, existing=None):
    """渲染條件輸入表單（僅回傳條件字典，不渲染 UI）。
    實際 UI 由 render_conditions_section() 統一渲染於全寬區域。"""
    cond = existing if existing else default_conditions()
    if not cond.get('fab_code'): cond['fab_code'] = detect_fab_code(dn)
    if not cond.get('region'): cond['region'] = detect_region(dn)
    return cond

def render_conditions_section(unique_dns, conds_dict, key_prefix):
    """在全寬區域渲染發包條件表單，以分頁(Tabs)切換每個專案，
    內部再以三區塊（工程特徵/發包條件/市場行情）分組，排版更寬敞。"""
    if not unique_dns:
        return conds_dict

    with st.expander("發包條件與市場行情（選填）", expanded=False):
        st.caption("記錄越完整，未來回歸預估越準確。所有欄位皆為選填。")
        st.write("")

        # 多專案用 tabs 切換；單專案直接顯示
        if len(unique_dns) > 1:
            tab_list = st.tabs(unique_dns)
        else:
            tab_list = [st.container()]

        for idx, dn in enumerate(unique_dns):
            with tab_list[idx]:
                cond = conds_dict.get(dn, default_conditions())
                if not cond.get('fab_code'): cond['fab_code'] = detect_fab_code(dn)
                if not cond.get('region'): cond['region'] = detect_region(dn)
                kp = f"{key_prefix}_{dn}"

                # ── 工程特徵 ──
                st.markdown('<div style="font-weight:600;color:var(--primary);font-size:.92rem;'
                            'margin-bottom:8px;"><span class="section-dot"></span>工程特徵</div>',
                            unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                with c1:
                    cond['fab_code'] = st.text_input("廠區代號", value=cond.get('fab_code', ''),
                                                      key=f"{kp}_fab", placeholder="如 AP7P1")
                with c2:
                    reg_opts = [''] + REGIONS
                    reg_idx = reg_opts.index(cond['region']) if cond.get('region') in reg_opts else 0
                    cond['region'] = st.selectbox("地區", reg_opts, index=reg_idx, key=f"{kp}_reg")
                with c3:
                    st_opts = [''] + STRUCT_TYPES
                    st_idx = st_opts.index(cond['struct_type']) if cond.get('struct_type') in st_opts else 0
                    cond['struct_type'] = st.selectbox("結構型式", st_opts, index=st_idx, key=f"{kp}_st")

                c4, c5 = st.columns(2)
                with c4:
                    cond['floors'] = st.number_input("樓層數", min_value=0,
                        value=int(cond.get('floors', 0)), key=f"{kp}_fl")
                with c5:
                    cond['duration_months'] = st.number_input("工期（月）", min_value=0,
                        value=int(cond.get('duration_months', 0)), key=f"{kp}_dur")

                st.write("")  # 區塊間距

                # ── 發包條件 ──
                st.markdown('<div style="font-weight:600;color:var(--primary);font-size:.92rem;'
                            'margin-bottom:8px;"><span class="section-dot"></span>發包條件</div>',
                            unsafe_allow_html=True)
                b1, b2, b3 = st.columns(3)
                with b1:
                    cm_opts = CONTRACT_MODES
                    cm_idx = cm_opts.index(cond['contract_mode']) if cond.get('contract_mode') in cm_opts else 0
                    cond['contract_mode'] = st.selectbox("發包方式", cm_opts, index=cm_idx, key=f"{kp}_cm")
                yn_opts = ['', '是', '否']
                with b2:
                    wm_idx = yn_opts.index(cond['with_material']) if cond.get('with_material') in yn_opts else 0
                    cond['with_material'] = st.selectbox("是否帶料", yn_opts, index=wm_idx, key=f"{kp}_wm")
                with b3:
                    we_idx = yn_opts.index(cond['with_equipment']) if cond.get('with_equipment') in yn_opts else 0
                    cond['with_equipment'] = st.selectbox("是否帶機具", yn_opts, index=we_idx, key=f"{kp}_we")

                st.write("")  # 區塊間距

                # ── 市場行情 ──
                st.markdown('<div style="font-weight:600;color:var(--primary);font-size:.92rem;'
                            'margin-bottom:8px;"><span class="section-dot"></span>市場行情</div>',
                            unsafe_allow_html=True)
                p1, p2 = st.columns(2)
                with p1:
                    cond['rebar_price'] = st.number_input("鋼筋（元/噸）", min_value=0,
                        value=int(cond.get('rebar_price', 0)), step=500, key=f"{kp}_reb")
                with p2:
                    cond['concrete_price'] = st.number_input("混凝土（元/m3）", min_value=0,
                        value=int(cond.get('concrete_price', 0)), step=100, key=f"{kp}_con")
                p3, p4 = st.columns(2)
                with p3:
                    cond['formwork_price'] = st.number_input("模板（元/m2）", min_value=0,
                        value=int(cond.get('formwork_price', 0)), step=50, key=f"{kp}_frm")
                with p4:
                    cond['price_index'] = st.number_input("營造物價指數", min_value=0.0,
                        value=float(cond.get('price_index', 0)), step=1.0, format="%.1f", key=f"{kp}_pi")

                st.write("")  # 區塊間距

                # ── 備註 ──
                cond['note'] = st.text_area("備註", value=cond.get('note', ''), key=f"{kp}_note",
                                             placeholder="特殊條件、趕工情形、同期競標量等", height=80)

                conds_dict[dn] = cond

    return conds_dict

# ═══════════════════════════════════════════════════════════════════
# SQLite
# ═══════════════════════════════════════════════════════════════════
def _db(): return sqlite3.connect(str(DB_FILE))

def init_db():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS assumption_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL, project_full TEXT, cutoff_date TEXT,
            read_date TEXT NOT NULL, area_ping REAL,
            total_budget REAL, total_settle REAL, items_json TEXT,
            source_filename TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_a_name ON assumption_snapshots(display_name, read_date)")
        c.execute("""CREATE TABLE IF NOT EXISTS cost_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL, project_full TEXT, read_date TEXT NOT NULL,
            area_ping REAL, area_m2 REAL, total_settle REAL,
            big_groups_json TEXT, items_json TEXT, unassigned_count INTEGER,
            source_filename TEXT, excel_blob BLOB, excel_filename TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_c_name ON cost_snapshots(display_name, read_date)")
        for tbl in ('assumption_snapshots', 'cost_snapshots'):
            try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN project_type TEXT DEFAULT '其他'")
            except: pass
            try: c.execute(f"ALTER TABLE {tbl} ADD COLUMN conditions_json TEXT DEFAULT '{{}}'")
            except: pass
init_db()

def db_insert_assumption(dn, pf, cd, ap, tb, ts, items, sf, file_date=None, project_type='其他', conditions=None):
    rd = file_date if file_date else datetime.now().strftime('%Y-%m-%d')
    cj = json.dumps(conditions or {}, ensure_ascii=False)
    with _db() as c:
        c.execute("""INSERT INTO assumption_snapshots
            (display_name, project_full, cutoff_date, read_date, area_ping,
             total_budget, total_settle, items_json, source_filename, project_type, conditions_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (dn, pf, cd, rd, ap, tb, ts, json.dumps(items, ensure_ascii=False), sf, project_type, cj))

def db_get_assumption_snaps(dn=None):
    c = _db(); c.row_factory = sqlite3.Row
    q = "SELECT * FROM assumption_snapshots"
    params = []
    if dn: q += " WHERE display_name = ?"; params.append(dn)
    q += " ORDER BY read_date ASC"
    rows = c.execute(q, params).fetchall(); c.close()
    out = []
    for r in rows:
        d = dict(r)
        d['items'] = json.loads(d.get('items_json') or '{}')
        d['conditions'] = json.loads(d.get('conditions_json') or '{}')
        out.append(d)
    return out

def db_get_all_assumption_names():
    c = _db()
    rows = c.execute("SELECT DISTINCT display_name FROM assumption_snapshots ORDER BY display_name").fetchall()
    c.close(); return [r[0] for r in rows]

def db_insert_cost(dn, pf, ap, am, ts, bg, items, un, sf, xb, xf, file_date=None, project_type='其他', conditions=None):
    rd = file_date if file_date else datetime.now().strftime('%Y-%m-%d')
    cj = json.dumps(conditions or {}, ensure_ascii=False)
    with _db() as c:
        c.execute("""INSERT INTO cost_snapshots
            (display_name, project_full, read_date, area_ping, area_m2,
             total_settle, big_groups_json, items_json, unassigned_count,
             source_filename, excel_blob, excel_filename, project_type, conditions_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (dn, pf, rd, ap, am, ts, json.dumps(bg, ensure_ascii=False),
             json.dumps(items, ensure_ascii=False), un, sf, xb, xf, project_type, cj))

def db_get_cost_snaps(dn=None):
    c = _db(); c.row_factory = sqlite3.Row
    cols = "id, display_name, project_full, read_date, area_ping, area_m2, total_settle, big_groups_json, items_json, unassigned_count, source_filename, excel_filename, project_type, conditions_json"
    q = f"SELECT {cols} FROM cost_snapshots"
    params = []
    if dn: q += " WHERE display_name = ?"; params.append(dn)
    q += " ORDER BY read_date ASC"
    rows = c.execute(q, params).fetchall(); c.close()
    out = []
    for r in rows:
        d = dict(r)
        d['big_groups'] = json.loads(d.get('big_groups_json') or '{}')
        d['items'] = json.loads(d.get('items_json') or '[]')
        d['conditions'] = json.loads(d.get('conditions_json') or '{}')
        out.append(d)
    return out

def db_get_all_cost_names():
    c = _db()
    rows = c.execute("SELECT DISTINCT display_name FROM cost_snapshots ORDER BY display_name").fetchall()
    c.close(); return [r[0] for r in rows]

def db_get_cost_excel(sid):
    c = _db()
    row = c.execute("SELECT excel_blob, excel_filename FROM cost_snapshots WHERE id=?", (sid,)).fetchone()
    c.close(); return (row[0], row[1]) if row else (None, None)

def db_delete_snapshot(table, sid):
    with _db() as c: c.execute(f"DELETE FROM {table} WHERE id=?", (sid,))

def db_clear_all(table):
    with _db() as c: c.execute(f"DELETE FROM {table}")

# ═══════════════════════════════════════════════════════════════════
# XML 解析（假設工程，與 v4 邏輯一致）
# ═══════════════════════════════════════════════════════════════════
NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def _parse_ref(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref); return m.group(1).upper(), int(m.group(2))

def read_xlsx_via_xml(filepath):
    data = {}; zf = zipfile.ZipFile(filepath); ss = []
    if 'xl/sharedStrings.xml' in zf.namelist():
        root = etree.parse(io.BytesIO(zf.read('xl/sharedStrings.xml')))
        for si in root.findall('.//ns:si', NS):
            ss.append(''.join(t.text for t in si.findall('.//ns:t', NS) if t.text))
    sf = sorted(f for f in zf.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml', f))
    if not sf: raise ValueError("找不到工作表")
    root = etree.parse(io.BytesIO(zf.read(sf[0])))
    for row in root.findall('.//ns:row', NS):
        for c in row.findall('ns:c', NS):
            ref = c.get('r'); t = c.get('t'); v = c.find('ns:v', NS); ie = c.find('ns:is', NS); val = None
            if ie is not None:
                val = ''.join(te.text for te in ie.findall('.//ns:t', NS) if te.text)
            elif t == 's' and v is not None and v.text:
                idx = int(v.text)
                if idx < len(ss): val = ss[idx]
            elif v is not None and v.text:
                val = v.text
            if val is not None:
                col, rn = _parse_ref(ref); data[(rn, col)] = val
    return data

def _f(v):
    try: return float(v)
    except: return 0.0

def _parent_subs(data, pr, rs):
    b = _f(data.get((pr,'M'),'0')); q = _f(data.get((pr,'Q'),'0')); w = _f(data.get((pr,'W'),'0'))
    for r in range(pr+1, pr+500):
        if r not in rs: continue
        if (r,'E') in data: break
        if (r,'S') in data:
            w += _f(data.get((r,'W'),'0')); q += _f(data.get((r,'Q'),'0'))
    return b, q, w

def _agg_c_code(data, rows, rs, pat):
    parents = [r for r in rows if pat in str(data.get((r,'C'),''))]
    bt = qt = wt = 0; done = set()
    for pr in parents:
        if pr in done: continue
        done.add(pr)
        bt += _f(data.get((pr,'M'),'0')); qt += _f(data.get((pr,'Q'),'0')); wt += _f(data.get((pr,'W'),'0'))
        for r in range(pr+1, pr+500):
            if r in done or r not in rs: continue
            if (r,'E') in data: break
            if (r,'S') in data:
                wt += _f(data.get((r,'W'),'0')); qt += _f(data.get((r,'Q'),'0')); done.add(r)
    return bt, qt, wt

def _find_f(data, rows, kw):
    return [r for r in rows if kw in str(data.get((r,'F'),'')) and (r,'E') in data]

def extract_categories(data):
    rows = sorted({r for r, _ in data.keys()}); rs = set(rows); cats = {}
    for nm, cd in [('租工','A.08.01'),('打石工','A.08.02'),('技術工','A.08.03'),
                   ('雜項工程','A.08.04'),('機具租金','A.08.05'),('零星建材','A.08.06')]:
        b, q, w = _agg_c_code(data, rows, rs, cd)
        cats[nm] = {'budget': b, 'contract': q, 'settlement': w}
    for nm, kw in [('安衛零星','安衛零星'),('雜支一','雜支一'),('雜支二','雜支二')]:
        prs = _find_f(data, rows, kw); bt = qt = wt = 0
        for pr in prs:
            b, q, w = _parent_subs(data, pr, rs); bt += b; qt += q; wt += w
        cats[nm] = {'budget': bt, 'contract': qt, 'settlement': wt}
    water = [r for r in rows if '水費' in str(data.get((r,'F'),''))
             and not any(x in str(data.get((r,'F'),'')) for x in ('飲水','排水','水電'))
             and (r,'E') in data]
    bt = qt = wt = 0
    for pr in water:
        b, q, w = _parent_subs(data, pr, rs); bt += b; qt += q; wt += w
    cats['水費'] = {'budget': bt, 'contract': qt, 'settlement': wt}
    elec = [r for r in rows if re.match(r'^電費', str(data.get((r,'F'),'')).strip()) and (r,'E') in data]
    bt = qt = wt = 0
    for pr in elec:
        b, q, w = _parent_subs(data, pr, rs); bt += b; qt += q; wt += w
    cats['電費'] = {'budget': bt, 'contract': qt, 'settlement': wt}
    phone = _find_f(data, rows, '電話費'); bt = qt = wt = 0
    for pr in phone:
        bt += _f(data.get((pr,'M'),'0')); qt += _f(data.get((pr,'Q'),'0')); wt += _f(data.get((pr,'W'),'0'))
    cats['電話費'] = {'budget': bt, 'contract': qt, 'settlement': wt}
    sal = _find_f(data, rows, '薪資'); bt = qt = wt = 0
    for pr in sal:
        b, q, w = _parent_subs(data, pr, rs); bt += b; qt += q; wt += w
    cats['人員薪資'] = {'budget': bt, 'contract': qt, 'settlement': wt}
    return cats

def get_project_info(data):
    return data.get((2,'B'), '未知專案'), data.get((3,'B'), '')

# ═══════════════════════════════════════════════════════════════════
# 共用工具
# ═══════════════════════════════════════════════════════════════════
def _parse_date_str(s):
    """從任意字串中擷取 YYYY-MM-DD，找不到回傳 None"""
    if not s: return None
    m = re.search(r'(\d{4})[-/\.](\d{2})[-/\.](\d{2})', str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

def extract_file_date(fp, cutoff_fallback=None):
    """日期優先順序：① 檔名內的日期 → ② 檔案內截止日（cutoff B3） → ③ 今天
    適用情境：
      有日期檔名  KG一覽表 (2026-04-24).xlsx → 2026-04-24
      有專案檔名  KG一覽表 (AP7P1-FAB).xlsx  → 從 cutoff B3 取得（例如 2026/03/31）
    """
    d = _parse_date_str(os.path.basename(str(fp)))
    if d: return d
    d = _parse_date_str(cutoff_fallback)
    if d: return d
    return datetime.now().strftime('%Y-%m-%d')

def extract_name_from_filename(fp):
    """從檔名括號內取專案名稱（非日期內容）
    KG一覽表 (AP7P1-FAB).xlsx  → 'AP7P1-FAB'
    KG一覽表 (2026-04-24).xlsx → None（是日期，不算）
    """
    fn = re.sub(r'\.xlsx?$', '', os.path.basename(str(fp)), flags=re.IGNORECASE)
    m = re.search(r'[（(]([^）)]+)[）)]', fn)
    if m:
        content = m.group(1).strip()
        if not _parse_date_str(content):   # 不是日期格式才當專案名稱
            return content
    return None

def clean_project_name(name):
    """清理從檔案內部讀取的專案名稱（B2 欄）"""
    if not name or name.strip() in ('', '未知專案'): return None
    return name.strip()[:40]

def extract_display_name(fp):
    """最終備用：從檔名推測顯示名稱"""
    fn = os.path.basename(str(fp))
    fn = re.sub(r'\.xlsx?$', '', fn, flags=re.IGNORECASE)
    fn = re.sub(r'^KG.*一覽表[_\s]*', '', fn)
    fn = re.sub(r'[_\s]*\d{4}[-\.]\d{2}[-\.]\d{2}[_\s]*$', '', fn)
    return fn.strip('_ ()（）') or os.path.basename(str(fp))

def db_check_duplicate(table, dn, read_date):
    """判斷同一專案同一日期是否已有快照"""
    c = _db()
    n = c.execute(f"SELECT COUNT(*) FROM {table} WHERE display_name=? AND read_date=?",
                  (dn, read_date)).fetchone()[0]
    c.close(); return n > 0

def load_areas():
    if AREA_FILE.exists():
        with open(AREA_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_areas(a):
    with open(AREA_FILE, 'w', encoding='utf-8') as f:
        json.dump(a, f, ensure_ascii=False, indent=2)

def fmt(n):
    if n is None or n == 0: return '-'
    if abs(n) >= 1e8: return f"{n/1e8:.2f}億"
    if abs(n) >= 1e4: return f"{n/1e4:,.0f}萬"
    return f"{n:,.0f}"

def fpp(n, p):
    if not n or not p or p < 10: return '-'
    return f"{n/p:,.0f}"

def _load_v14():
    try: sd = Path(__file__).parent
    except NameError: sd = Path('.')
    for p in [sd/'kg_cost_analysis_v14.py', Path('.')/'kg_cost_analysis_v14.py']:
        if p.exists():
            spec = importlib.util.spec_from_file_location("v14", str(p))
            mod = importlib.util.module_from_spec(spec)
            old = sys.argv; sys.argv = ['']
            try: spec.loader.exec_module(mod)
            finally: sys.argv = old
            return mod
    return None

# ═══════════════════════════════════════════════════════════════════
# 視覺樣式（統一、精簡、去 emoji 雜訊）
# ═══════════════════════════════════════════════════════════════════
def inject_style():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@300;400;500;600;700&display=swap');
    :root {
        --bg:#F4F7FB; --surface:#ffffff; --surface-2:#F8FAFC; --surface-3:#F1F5F9;
        --primary:#1D4ED8; --primary-50:#EFF6FF; --primary-100:#DBEAFE; --primary-300:#93C5FD;
        --action:#3B82F6;
        --text:#0F1729; --text-2:#334155; --muted:#64748B;
        --accent:#DBEAFE;
        --amber:#D97706; --amber-light:#FEF3C7; --amber-glow:rgba(217,119,6,0.12);
        --good:#059669; --good-light:#D1FAE5;
        --bad:#DC2626; --bad-light:#FEE2E2;
        --border:#E2E8F0; --header-bg:#F8FAFC;
        --card-shadow:0 1px 2px rgba(15,23,41,.04),0 1px 3px rgba(15,23,41,.06);
        --card-shadow-hover:0 4px 12px rgba(15,23,41,.08),0 2px 6px rgba(15,23,41,.04);
        --mono:"JetBrains Mono","Fira Code","Roboto Mono",ui-monospace,Consolas,monospace;
        --radius:12px; --radius-sm:8px; --radius-lg:16px;
    }
    html, body, [class*="css"], .stApp {
        font-family: "Noto Sans TC","Microsoft JhengHei",-apple-system,"Segoe UI",sans-serif;
        color: var(--text);
    }
    .stApp { background: var(--bg); }
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1280px; }
    [data-testid="stHeader"] { background: transparent; }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: var(--surface); border-right: 1px solid var(--border);
        box-shadow: 1px 0 4px rgba(15,23,41,.03);
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label {
        font-size: .9rem; font-weight: 500; padding: 8px 12px;
        border-radius: var(--radius-sm); transition: background .15s;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: var(--primary-50);
    }

    /* Page header pattern */
    .crumb { font-size: 12px; color: var(--muted); margin-bottom: 4px; letter-spacing: .3px; }
    .page-title { font-weight: 700 !important; font-size: 24px !important; color: var(--text) !important;
         background: none !important; -webkit-text-fill-color: var(--text) !important;
         margin-bottom: 4px !important; letter-spacing: 0 !important; }
    .page-sub { font-size: 13px; color: var(--muted); margin-bottom: 1.2rem; }

    h1 { font-weight: 700; font-size: 1.5rem; margin-bottom: .3rem;
         letter-spacing: 0; color: var(--text); }
    h2 { font-weight: 600; font-size: 1.1rem; margin-top: 1.6rem; margin-bottom: .7rem;
         color: var(--text-2); letter-spacing: .2px;
         padding-bottom: .35rem; border-bottom: 2px solid var(--primary-100); display: inline-block; }
    h3 { font-weight: 600; font-size: 1rem; color: var(--text-2); margin-top: 1rem; }
    h4, h5 { font-weight: 600; color: var(--text-2); }
    p, label, .stMarkdown { color: var(--text); }
    [data-testid="stCaptionContainer"], .stCaption, small { color: var(--muted) !important; }

    /* KPI / Metric card — left 3px accent stripe */
    [data-testid="stMetric"] {
        background: var(--surface);
        padding: 16px 20px 16px 18px; border-radius: var(--radius);
        border: 1px solid var(--border);
        border-left: 3px solid var(--action);
        box-shadow: var(--card-shadow);
        transition: all .2s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: var(--card-shadow-hover);
        transform: translateY(-1px);
    }
    [data-testid="stMetricLabel"] p {
        font-size:11.5px !important; color: var(--muted) !important;
        font-weight:600; letter-spacing:.8px; text-transform: uppercase;
    }
    [data-testid="stMetricValue"] {
        font-size:26px !important; font-weight:700; color: var(--text) !important;
        font-family: var(--mono); letter-spacing: 0;
    }
    [data-testid="stMetricDelta"] { font-size:.78rem !important; }
    [data-testid="stMetricDelta"] svg { width: 14px; height: 14px; }

    /* Buttons — ghost default, gradient primary */
    .stButton>button, .stDownloadButton>button {
        border-radius: var(--radius-sm); font-weight: 600; font-size: 13px; letter-spacing: .2px;
        border: 1px solid var(--border); color: var(--text-2); background: var(--surface);
        padding: .5rem 1.2rem; cursor: pointer;
        transition: all .2s cubic-bezier(.4,0,.2,1);
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        background: var(--surface-2); border-color: var(--action); color: var(--primary);
        box-shadow: 0 2px 6px rgba(59,130,246,0.1);
    }
    .stButton>button[kind="primary"], .stDownloadButton>button[kind="primary"] {
        background: linear-gradient(135deg, #1D4ED8 0%, #3B82F6 100%);
        border-color: transparent; color: #ffffff;
        box-shadow: 0 2px 8px rgba(29,78,216,0.25);
    }
    .stButton>button[kind="primary"]:hover, .stDownloadButton>button[kind="primary"]:hover {
        background: linear-gradient(135deg, #1E40AF 0%, #2563EB 100%);
        box-shadow: 0 4px 12px rgba(30,64,175,0.3); transform: translateY(-1px);
    }
    .stButton>button:disabled {
        background: var(--surface-3); color: #CBD5E1; border-color: var(--border); box-shadow: none;
    }

    /* File uploader / Dropzone */
    div[data-testid="stFileUploader"] section {
        padding: 1.4rem; border: 2px dashed var(--primary-300); border-radius: var(--radius);
        background: var(--primary-50);
        transition: all .2s ease;
    }
    div[data-testid="stFileUploader"] section:hover {
        border-color: var(--action); background: var(--primary-100);
        box-shadow: 0 4px 12px rgba(59,130,246,0.08);
    }

    /* Tabs — pill style */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px; border-bottom: 2px solid var(--border);
        padding-bottom: 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: .9rem; padding: 8px 20px; border-radius: 8px 8px 0 0;
        color: var(--muted); font-weight: 500;
        transition: all .15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--accent) !important; color: var(--primary) !important;
    }
    .stTabs [aria-selected="true"] {
        background: var(--surface) !important; color: var(--primary) !important;
        font-weight: 700; border-bottom: 3px solid var(--amber) !important;
        box-shadow: 0 -2px 8px rgba(30,64,175,0.06);
    }

    /* 強制淺色 */
    [data-baseweb="input"],
    [data-baseweb="input"] > div,
    [data-baseweb="input"] > div > div,
    [data-baseweb="select"] > div,
    [data-baseweb="select"] > div > div,
    [data-baseweb="textarea"],
    [data-baseweb="textarea"] > div,
    .stNumberInput > div > div,
    .stTextInput > div > div,
    .stDateInput > div > div {
        background: #FFFFFF !important;
        border-color: var(--border) !important;
        border-radius: 8px !important;
    }
    [data-baseweb="input"] input,
    [data-baseweb="select"] input,
    [data-baseweb="textarea"] textarea,
    .stNumberInput input,
    .stTextInput input,
    .stDateInput input,
    input[type="text"], input[type="number"], input[type="search"], textarea {
        background: #FFFFFF !important;
        color: var(--text) !important;
        caret-color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        font-weight: 500 !important;
    }
    [data-baseweb="input"]:focus-within,
    [data-baseweb="select"] > div:focus-within {
        border-color: var(--action) !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.12) !important;
    }
    .stNumberInput button,
    [data-testid="stNumberInput"] button {
        background: #F8FAFC !important;
        color: var(--primary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    .stNumberInput button:hover,
    [data-testid="stNumberInput"] button:hover {
        background: var(--accent) !important;
    }
    [data-baseweb="select"] > div > div > div,
    [data-baseweb="select"] [data-baseweb="tag"] {
        color: var(--text) !important;
        font-weight: 500 !important;
    }
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    [role="listbox"] {
        background: #FFFFFF !important;
        border-radius: var(--radius) !important;
        box-shadow: 0 8px 30px rgba(15,23,42,0.12), 0 2px 8px rgba(15,23,42,0.06) !important;
    }
    [data-baseweb="popover"] [role="option"],
    [data-baseweb="popover"] li,
    [role="listbox"] > li,
    [role="listbox"] [role="option"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
        padding: 10px 14px !important;
        font-size: .9rem !important;
        transition: background .12s ease;
    }
    [data-baseweb="popover"] [role="option"]:hover,
    [data-baseweb="popover"] li:hover,
    [role="listbox"] [role="option"]:hover {
        background: var(--accent) !important;
        color: var(--primary) !important;
    }
    [data-baseweb="popover"] [role="option"][aria-selected="true"],
    [role="listbox"] [role="option"][aria-selected="true"] {
        background: var(--accent) !important;
        color: var(--primary) !important;
        font-weight: 700 !important;
    }
    [data-baseweb="tag"] {
        background: var(--accent) !important;
        color: var(--primary) !important;
        border-radius: 999px !important;
    }
    [data-testid="stModal"],
    [role="dialog"],
    [data-baseweb="modal"],
    [data-baseweb="modal"] > div,
    [data-testid="stToast"],
    [data-baseweb="toast"] {
        background: #FFFFFF !important;
        color: var(--text) !important;
    }
    [role="tooltip"], [data-baseweb="tooltip"] {
        background: var(--text) !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
    }
    [data-baseweb="checkbox"] span, [data-baseweb="radio"] span {
        color: var(--text) !important;
    }

    /* Table */
    .stDataFrame, [data-testid="stDataFrame"] {
        border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden;
        background: var(--surface); box-shadow: var(--card-shadow);
    }
    .stDataFrame thead tr th, [data-testid="stDataFrame"] thead tr th {
        background: var(--surface-2) !important;
        color: var(--muted) !important;
        font-weight: 600 !important; font-size: 11.5px !important;
        letter-spacing: .5px; text-transform: uppercase;
        border-bottom: 2px solid var(--border) !important;
        border-right: none !important; border-left: none !important;
    }
    .stDataFrame tbody tr td, [data-testid="stDataFrame"] tbody tr td {
        border-right: none !important; border-left: none !important;
        border-bottom: 1px solid #F1F5F9 !important;
        color: var(--text) !important;
    }
    .mono-num, table.dashboard-table td.num {
        font-family: var(--mono) !important; text-align: right !important;
        font-variant-numeric: tabular-nums;
    }

    table.dashboard-table {
        width: 100%; border-collapse: collapse; background: var(--surface);
        border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden;
        font-size: .88rem;
    }
    table.dashboard-table thead th {
        background: var(--surface-2); color: var(--muted);
        font-weight: 600; font-size: 11.5px; letter-spacing: .5px;
        text-transform: uppercase;
        padding: 12px 14px; text-align: left;
        border-bottom: 2px solid var(--border);
    }
    table.dashboard-table tbody td {
        padding: 10px 14px; border-bottom: 1px solid #F1F5F9;
        color: var(--text);
    }
    table.dashboard-table tbody tr:last-child td { border-bottom: none; }
    table.dashboard-table tbody tr:hover { background: #F0F7FF; }

    .pill {
        display: inline-block; padding: 3px 12px; border-radius: 999px;
        background: var(--accent); color: var(--primary);
        font-size: .76rem; font-weight: 600; letter-spacing: .3px;
        line-height: 1.5;
    }
    .pill-amber {
        background: var(--amber-light); color: var(--amber);
    }
    .pill-muted { background: #F1F5F9; color: var(--muted); }

    /* Nav card (home page) */
    .nav-card {
        background: var(--surface); border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 22px 20px; transition: all .2s ease;
        box-shadow: var(--card-shadow);
    }
    .nav-card:hover {
        border-color: var(--action);
        box-shadow: var(--card-shadow-hover);
        transform: translateY(-2px);
    }
    .nav-card-icon {
        width: 40px; height: 40px; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
        margin-bottom: 12px; font-size: 18px;
    }
    .nav-icon-blue { background: var(--primary-50); color: var(--primary); }
    .nav-icon-amber { background: var(--amber-light); color: var(--amber); }
    .nav-icon-green { background: var(--good-light); color: var(--good); }
    .nav-icon-purple { background: #EDE9FE; color: #5B21B6; }

    [data-testid="stExpander"] {
        border-radius: var(--radius); border: 1px solid var(--border) !important;
        background: var(--surface);
        box-shadow: var(--card-shadow);
        transition: box-shadow .2s ease;
    }
    [data-testid="stExpander"]:hover {
        box-shadow: var(--card-shadow-hover);
    }
    [data-testid="stExpander"] summary { font-weight: 600; color: var(--primary); }

    [data-testid="stAlert"] {
        border-radius: var(--radius); border-left-width: 4px;
        box-shadow: 0 1px 4px rgba(15,23,42,0.04);
    }

    .muted { color: var(--muted); font-size: .82rem; }
    hr { margin: 1.4rem 0; border: none; border-top: 1px solid var(--border); }

    .js-plotly-plot .plotly .bg { fill: transparent !important; }

    /* Section divider with amber dot */
    .section-dot { display: inline-block; width: 8px; height: 8px;
        border-radius: 50%; background: var(--amber); margin-right: 8px;
        vertical-align: middle; }
    </style>""", unsafe_allow_html=True)


def render_logo_bar():
    """頁面頂端的 LOGO 橫條。若 logo.png 不存在則顯示純文字"""
    if LOGO_FILE.exists():
        import base64
        try:
            b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode()
            st.markdown(
                f'''<div class="logo-bar">
                    <img src="data:image/png;base64,{b64}" alt="根基營造">
                    <div style="display:flex;flex-direction:column;">
                        <span class="logo-bar-text">根基營造　KEDGE CONSTRUCTION</span>
                        <span class="logo-tagline">COST MANAGEMENT SYSTEM</span>
                    </div>
                </div>''',
                unsafe_allow_html=True,
            )
            return
        except Exception:
            pass
    st.markdown(
        '''<div class="logo-bar">
            <div style="display:flex;flex-direction:column;">
                <span class="logo-bar-text">根基營造　KEDGE CONSTRUCTION</span>
                <span class="logo-tagline">COST MANAGEMENT SYSTEM</span>
            </div>
        </div>''',
        unsafe_allow_html=True,
    )

def back_button():
    c1, _ = st.columns([1, 9])
    with c1:
        if st.button("← 回首頁", key=f"back_{st.session_state.get('page','')}", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith(('a_','v14_','_a_','_v14_','confirm_')):
                    st.session_state.pop(k, None)
            st.session_state['page'] = 'home'; st.rerun()

def area_input(dn, areas, key_prefix):
    """面積輸入：坪 與 m² 並排，兩者自動同步（任一更動另一個會跟著變）"""
    saved_ping = float(areas.get(dn, 0.0))
    kp = f"{key_prefix}_ping_{dn}"
    km = f"{key_prefix}_m2_{dn}"

    # 初始化 session_state（只在第一次進入時）
    if kp not in st.session_state:
        st.session_state[kp] = round(saved_ping, 0)
        st.session_state[km] = round(saved_ping * M2_PER_PING, 0)
    elif km not in st.session_state:
        st.session_state[km] = round(st.session_state[kp] * M2_PER_PING, 0)

    def _sync_from_ping():
        st.session_state[km] = round(st.session_state[kp] * M2_PER_PING, 0)

    def _sync_from_m2():
        st.session_state[kp] = round(st.session_state[km] * PING_PER_M2, 0)

    st.markdown(f"**{dn}**")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input(
            "坪", min_value=0.0, step=100.0, key=kp, format="%.0f",
            on_change=_sync_from_ping, label_visibility="visible",
        )
    with c2:
        st.number_input(
            "m²", min_value=0.0, step=100.0, key=km, format="%.0f",
            on_change=_sync_from_m2, label_visibility="visible",
        )
    ping = float(st.session_state[kp])
    m2 = float(st.session_state[km])
    if ping > 0 or m2 > 0:
        st.caption(f"{ping:,.0f} 坪　≈　{m2:,.0f} m²")
    else:
        st.caption("尚未設定（任一欄位輸入即可，另一欄會自動換算）")
    return ping

def sync_area(dn, ping, areas):
    if ping > 0 and abs(areas.get(dn, 0) - ping) > 0.001:
        areas[dn] = ping; save_areas(areas); return True
    return False

# ═══════════════════════════════════════════════════════════════════
# 主程式
# ═══════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(page_title="成本管理監測系統", page_icon="◆",
                       layout="wide", initial_sidebar_state="expanded")
    inject_style()

    # Sidebar navigation
    with st.sidebar:
        st.markdown(
            '<div style="padding:8px 0 16px 0;">'
            '<div style="font-weight:700;font-size:1.1rem;color:var(--text);">根基營造</div>'
            '<div style="font-size:12px;color:var(--muted);letter-spacing:1px;">KEDGE · 成本監測</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        page_map = {
            "總覽儀表板": "home",
            "假設工程分析": "assumption",
            "造價分析": "cost_analysis",
            "投標預估": "prediction",
            "歷史記錄": "history",
        }
        if 'page' not in st.session_state:
            st.session_state['page'] = 'home'
        current_label = [k for k, v in page_map.items() if v == st.session_state['page']]
        current_label = current_label[0] if current_label else "總覽儀表板"
        selected = st.radio("導航", list(page_map.keys()), index=list(page_map.keys()).index(current_label),
                            label_visibility="collapsed")
        if page_map[selected] != st.session_state['page']:
            st.session_state['page'] = page_map[selected]
            st.rerun()

    p = st.session_state['page']
    if p == 'home': page_home()
    elif p == 'assumption': page_assumption()
    elif p == 'cost_analysis': page_cost_analysis()
    elif p == 'history': page_history()
    elif p == 'prediction': page_prediction()

# ═══════════════════════════════════════════════════════════════════
# 首頁
# ═══════════════════════════════════════════════════════════════════
def page_home():
    st.markdown('<div class="crumb">總覽</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">總覽儀表板</h1>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">KG 一覽表分析 · 假設工程追蹤 · 造價統計 · 投標預估</div>', unsafe_allow_html=True)
    st.write("")

    v14 = _load_v14()
    nav = [
        ("假設工程分析", "13 項假設工程結算追蹤 · 跨期比對", "assumption", True, "blue",
         '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>'),
        ("造價分析", "八大類工程造價統計 · 產出 Excel", "cost_analysis", v14 is not None, "amber",
         '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 5 5-9"/></svg>'),
        ("投標預估", "依類型回歸預估 · 面積推算造價", "prediction", True, "green",
         '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'),
        ("歷史記錄", "查看過往快照 · 下載 Excel · 趨勢圖", "history", True, "purple",
         '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="10"/><path d="M3.05 11a9 9 0 0118 0"/></svg>'),
    ]
    cols = st.columns(4, gap="medium")
    for (title, desc, target, enabled, color, icon), col in zip(nav, cols):
        with col:
            st.markdown(
                f'''<div class="nav-card">
                    <div class="nav-card-icon nav-icon-{color}">{icon}</div>
                    <div style="font-weight:700;font-size:1rem;color:var(--primary);margin-bottom:6px;">{title}</div>
                    <div class="muted">{desc}</div>
                </div>''',
                unsafe_allow_html=True,
            )
            st.write("")
            if enabled:
                if st.button("進入  →", key=f"nav_{target}", use_container_width=True, type="primary"):
                    st.session_state['page'] = target; st.rerun()
            else:
                st.button("缺少 kg_cost_analysis_v14.py", disabled=True, use_container_width=True, key=f"nav_{target}")

    # 最近分析
    st.markdown("## 最近分析")
    rows = []
    for dn in db_get_all_assumption_names():
        snaps = db_get_assumption_snaps(dn)
        if snaps:
            s = snaps[-1]; ap = s.get('area_ping', 0) or 0
            rows.append({'類型':'假設工程','專案':dn,'最近更新':s['read_date'][:10],
                         '結算':fmt(s.get('total_settle', 0)),
                         '元/坪':fpp(s.get('total_settle', 0), ap),
                         '快照':len(snaps)})
    for dn in db_get_all_cost_names():
        snaps = db_get_cost_snaps(dn)
        if snaps:
            s = snaps[-1]; ap = s.get('area_ping', 0) or 0
            rows.append({'類型':'造價分析','專案':dn,'最近更新':s['read_date'][:10],
                         '結算':fmt(s.get('total_settle', 0)),
                         '元/坪':fpp(s.get('total_settle', 0), ap),
                         '快照':len(snaps)})
    if rows:
        df = pd.DataFrame(rows).sort_values('最近更新', ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("尚未有分析記錄。上方任一功能皆可開始。")

# ═══════════════════════════════════════════════════════════════════
# 假設工程分析
# ═══════════════════════════════════════════════════════════════════
def page_assumption():
    st.markdown('<div class="crumb">總覽 / 假設工程分析</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">假設工程分析</h1>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">上傳 KG 一覽表 · 設定面積 · 即時預覽 · 儲存快照</div>', unsafe_allow_html=True)
    areas = load_areas()

    # 1. 上傳
    st.markdown("## 匯入 KG 一覽表")
    uc1, uc2 = st.columns([3, 1])
    with uc1:
        uploaded = st.file_uploader("拖拉或選擇 .xlsx（可多選）",
            type=['xlsx'], accept_multiple_files=True, key='a_up',
            label_visibility='collapsed')
    with uc2:
        st.write("")
        if st.button("從 kg_data/ 掃描", use_container_width=True, key='a_sc'):
            found = list(DATA_DIR.glob('*.xlsx'))
            if found:
                st.session_state['a_folder'] = found
                st.toast(f"掃描到 {len(found)} 個檔案")
            else:
                st.toast("資料夾內無 .xlsx 檔案", icon='warning')

    to_proc = []
    if uploaded:
        for uf in uploaded:
            tmp = DATA_DIR / uf.name
            with open(tmp, 'wb') as f: f.write(uf.getbuffer())
            to_proc.append(str(tmp))
    if 'a_folder' in st.session_state:
        to_proc.extend([str(f) for f in st.session_state['a_folder']])

    # 無上傳 → 顯示歷史最新快照
    if not to_proc:
        names = db_get_all_assumption_names()
        if names:
            latest = [db_get_assumption_snaps(dn)[-1] for dn in names if db_get_assumption_snaps(dn)]
            if latest:
                st.markdown("## 目前已儲存的專案（最新快照）")
                _render_assumption(latest, areas)
        else:
            st.info("上傳 .xlsx 後即可自動分析")
        return

    # 解析（以檔名 hash 快取）—— parsed 為 list，允許同名專案不同日期並存
    h = str(sorted(to_proc))
    if st.session_state.get('_a_hash') != h:
        parsed_list = []
        with st.spinner("解析 KG 一覽表..."):
            for fp in to_proc:
                try:
                    raw = read_xlsx_via_xml(fp)
                    proj_name, cutoff = get_project_info(raw)
                    cats = extract_categories(raw)
                    # 名稱優先：B2 → 括號內非日期文字 → 備用
                    dn = (clean_project_name(proj_name)
                          or extract_name_from_filename(fp)
                          or extract_display_name(fp))
                    # 日期優先：① B3 截止日（最可靠）→ ② 檔名日期 → ③ 今天
                    # 完全不依賴檔名作為主要來源，避免 (1)(2) 後綴干擾
                    file_date = (_parse_date_str(cutoff)
                                 or _parse_date_str(os.path.basename(fp))
                                 or datetime.now().strftime('%Y-%m-%d'))
                    parsed_list.append({'dn':dn, 'proj':proj_name, 'cutoff':cutoff,
                                        'cats':cats, 'filename':os.path.basename(fp),
                                        'file_date':file_date})
                except Exception as e:
                    st.error(f"{os.path.basename(fp)}: {e}")
        # 同一批次若有完全相同的 (dn, file_date) 則警告並去重
        seen = set(); deduped = []
        for item in parsed_list:
            key = (item['dn'], item['file_date'])
            if key in seen:
                st.warning(f"同批次重複：**{item['dn']}** 日期 {item['file_date']}，略過 {item['filename']}")
            else:
                seen.add(key); deduped.append(item)
        st.session_state['a_parsed'] = deduped
        st.session_state['_a_hash'] = h

    parsed_list = st.session_state.get('a_parsed', [])
    if not parsed_list: return

    # 2. 面積 + 專案類型
    st.markdown("## 設定面積與專案類型")
    unique_dns = list(dict.fromkeys(item['dn'] for item in parsed_list))
    n = min(len(unique_dns), 4)
    cols = st.columns(n if n >= 2 else 1)
    areas_now = {}; types_now = {}; conds_now = {}
    for i, dn in enumerate(unique_dns):
        with cols[i % len(cols)]:
            areas_now[dn] = area_input(dn, areas, 'a')
            guessed = detect_project_type(dn)
            idx = PROJECT_TYPES.index(guessed) if guessed in PROJECT_TYPES else len(PROJECT_TYPES) - 1
            types_now[dn] = st.selectbox("專案類型", PROJECT_TYPES, index=idx, key=f"a_type_{dn}")
            conds_now[dn] = render_conditions_input(dn, 'a_cond')
            h_count = len(db_get_assumption_snaps(dn))
            if h_count: st.caption(f"已有歷史 {h_count} 筆")
    conds_now = render_conditions_section(unique_dns, conds_now, 'a_cond')
    for dn, ap in areas_now.items():
        sync_area(dn, ap, areas)

    # 3. 即時預覽結果（每個檔案一筆，同名專案不同日期各自獨立）
    results = []
    for info in parsed_list:
        dn = info['dn']; cats = info['cats']
        ping = areas_now.get(dn) or areas.get(dn, 0)
        items = {k:{'budget':cats[k]['budget'],'settlement':cats[k]['settlement']} for k in ORDER}
        tb = sum(cats[k]['budget'] for k in ORDER)
        ts = sum(cats[k]['settlement'] for k in ORDER)
        results.append({
            'display_name':dn, 'project':info['proj'], 'cutoff':info['cutoff'],
            'area_ping':ping, 'total_budget':tb, 'total_settle':ts, 'items':items,
            'read_date':info['file_date'], '_info':info,
        })

    # 顯示解析結果：依「專案名稱」分組呈現，凸顯哪些可畫趨勢
    from collections import defaultdict
    proj_dates = defaultdict(list)
    risky = []
    for info in parsed_list:
        proj_dates[info['dn']].append((info['file_date'], info))
        # 風險檔案：B2/B3 皆空，名稱與日期都用備援
        b2_empty = not clean_project_name(info.get('proj', ''))
        b3_empty = not _parse_date_str(info.get('cutoff'))
        fn_date = _parse_date_str(os.path.basename(info['filename']))
        if b2_empty and b3_empty and not fn_date:
            risky.append(info)

    # 主要訊息：專案 × 日期列表，標示可否畫趨勢
    lines = []
    for dn, pairs in proj_dates.items():
        pairs.sort(key=lambda x: x[0])
        date_str = " → ".join(p[0] for p in pairs)
        tag = "📈 可畫趨勢" if len(pairs) >= 2 else "　單點"
        lines.append(f"{tag}　**{dn}**　{date_str}")
    st.info("識別結果（名稱來自檔案 B2，日期來自 B3 截止日）：\n\n" + "\n\n".join(lines))

    # 風險檔案另外警告
    if risky:
        names = "、".join(r['filename'] for r in risky)
        st.warning(f"(!) 以下檔案的 B2 專案名稱與 B3 截止日皆為空，系統以檔名備援+今日代替，"
                   f"請確認內容：{names}")

    # 結果區 + 儲存按鈕
    sc1, sc2 = st.columns([4, 1])
    with sc1: st.markdown("## 分析結果（即時預覽）")
    with sc2:
        st.write("")
        if st.button("儲存快照", use_container_width=True, type="primary", key='a_save'):
            saved = skipped = 0
            for r in results:
                info = r['_info']
                rd = r['read_date']
                if db_check_duplicate('assumption_snapshots', r['display_name'], rd):
                    st.warning(f"**{r['display_name']}** 日期 {rd} 已存在，略過（如需覆蓋請先至歷史記錄刪除）")
                    skipped += 1
                else:
                    pt = types_now.get(r['display_name'], '其他')
                    cd = conds_now.get(r['display_name'], {})
                    db_insert_assumption(r['display_name'], info['proj'], info['cutoff'],
                        r['area_ping'], r['total_budget'], r['total_settle'],
                        r['items'], info['filename'], file_date=rd, project_type=pt, conditions=cd)
                    saved += 1
            if saved:
                st.toast(f"已儲存 {saved} 筆快照", icon='✅')
            elif skipped:
                st.toast("全部已存在，未新增", icon='warning')
            st.rerun()

    _render_assumption(results, areas)


def _render_assumption(results, areas):
    from collections import Counter
    dn_counts = Counter(d.get('display_name', '') for d in results)
    # 概覽
    cols = st.columns(min(len(results), 5))
    for col, d in zip(cols, results):
        dn = d.get('display_name', ''); ap = areas.get(dn, d.get('area_ping', 0)) or 0
        label = f"{dn}\n{d.get('read_date','')}" if dn_counts[dn] > 1 else dn
        with col:
            st.metric(label, fmt(d.get('total_settle', 0)), f"預算 {fmt(d.get('total_budget', 0))}")
            if ap >= 10: st.caption(f"{fpp(d['total_settle'], ap)} 元/坪")

    # 跨專案比較
    if len(results) > 1:
        with st.expander("跨專案比較（結算金額）"):
            fig = go.Figure()
            for d in results:
                items = d.get('items', {})
                vals = [items.get(n, {}).get('settlement', 0) if isinstance(items.get(n), dict) else 0 for n in ORDER]
                fig.add_trace(go.Bar(x=ORDER, y=vals, name=d.get('display_name', ''),
                    text=[fmt(v) if v > 0 else '' for v in vals],
                    textposition='outside', textfont=dict(size=9)))
            fig.update_layout(barmode='group', height=360, margin=dict(l=10, r=10, t=10, b=60),
                font=dict(family="Microsoft JhengHei"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

    # 每個專案的分頁：同名專案出現多次時，加上日期區分
    from collections import Counter
    dn_counts = Counter(d.get('display_name', '') for d in results)
    tab_labels = [
        f"{d.get('display_name','')} · {d.get('read_date','')}"
        if dn_counts[d.get('display_name', '')] > 1
        else d.get('display_name', '')
        for d in results
    ]
    tabs = st.tabs(tab_labels)
    for tab, d in zip(tabs, results):
        # 把整批當前結果一併傳入，讓趨勢可以合併尚未儲存的快照
        with tab: _render_assumption_project(d, areas, all_current=results)


def _render_assumption_project(data, areas, all_current=None):
    dn = data.get('display_name', '')
    all_snaps = db_get_assumption_snaps(dn)
    cur_date = data.get('read_date', '')
    # 「上次」的比較對象：先看本批同專案更早的檔案，再看資料庫
    cur_same = [r for r in (all_current or []) if r.get('display_name') == dn
                and r.get('read_date', '') < cur_date]
    if cur_same:
        prev = sorted(cur_same, key=lambda r: r['read_date'])[-1]
    else:
        prev_snaps = [s for s in all_snaps if s.get('read_date', '') < cur_date]
        prev = prev_snaps[-1] if prev_snaps else None
    ping = areas.get(dn, data.get('area_ping', 0)) or 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        delta = None
        if prev:
            diff = data['total_settle'] - prev.get('total_settle', 0)
            delta = f"{'+' if diff > 0 else ''}{fmt(diff)}"
        st.metric("結算合計", fmt(data['total_settle']), delta)
    with c2: st.metric("預算合計", fmt(data['total_budget']))
    with c3:
        d2 = data['total_settle'] - data['total_budget']
        st.metric("差異", fmt(d2), "超出" if d2 > 0 else "結餘")
    with c4:
        if ping >= 10:
            st.metric("結算元/坪", f"{data['total_settle']/ping:,.0f}",
                      f"預算 {data['total_budget']/ping:,.0f}")
        else:
            st.metric("結算元/坪", "—", "未設面積")

    info = [f"截止日 {data.get('cutoff', '-')}", data.get('project', '')]
    if prev: info.append(f"上次 {prev.get('read_date', '')[:10]} / 結算 {fmt(prev.get('total_settle', 0))}")
    st.caption("　·　".join(x for x in info if x))

    t1, t2 = st.tabs(["分析表", "歷史趨勢"])
    with t1: _tab_assumption_table(data, prev, ping)
    with t2: _tab_assumption_trend(dn, all_current=all_current)


def _tab_assumption_table(data, prev, ping):
    items = data.get('items', {})
    pi = prev.get('items', {}) if prev else {}
    def g(it, n, f):
        v = it.get(n)
        return v.get(f, 0) if isinstance(v, dict) else ((v or 0) if f == 'settlement' else 0)

    rows = []
    for n in ORDER:
        b = g(items, n, 'budget'); s = g(items, n, 'settlement')
        ps = g(pi, n, 'settlement'); diff = s - ps if prev else 0
        ds = ''
        if prev and diff: ds = f"{'+' if diff > 0 else ''}{fmt(diff)}"
        elif prev: ds = '持平'
        rows.append({
            '工程項目': n,
            '預算金額': fmt(b),
            '元/坪(預)': f"{b/ping:,.0f}" if ping >= 10 and b else '-',
            '結算金額': fmt(s),
            '元/坪(結)': f"{s/ping:,.0f}" if ping >= 10 and s else '-',
            '差異': fmt(s - b) if b else '-',
            '本次增減': ds,
        })
    tb = sum(g(items, n, 'budget') for n in ORDER)
    ts = sum(g(items, n, 'settlement') for n in ORDER)
    tps = sum(g(pi, n, 'settlement') for n in ORDER) if prev else 0
    rows.append({
        '工程項目': '合計', '預算金額': fmt(tb),
        '元/坪(預)': f"{tb/ping:,.0f}" if ping >= 10 else '-',
        '結算金額': fmt(ts),
        '元/坪(結)': f"{ts/ping:,.0f}" if ping >= 10 else '-',
        '差異': fmt(ts - tb),
        '本次增減': f"{'+' if ts - tps > 0 else ''}{fmt(ts - tps)}" if prev else '',
    })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=540)


def _tab_assumption_trend(dn, all_current=None):
    # 合併：資料庫已存快照 + 本次批次中尚未儲存的同專案結果
    db_snaps = db_get_assumption_snaps(dn)
    combined = {s['read_date'][:10]: {
        'read_date': s['read_date'], 'total_settle': s.get('total_settle', 0),
        'total_budget': s.get('total_budget', 0), 'items': s.get('items', {}),
        '_source': 'db',
    } for s in db_snaps}
    # 把當前批次中屬於此專案的都加進去（含本期自己）
    for r in (all_current or []):
        if r.get('display_name') != dn: continue
        k = r.get('read_date', '')[:10]
        if k and k not in combined:   # 已儲存過則以 DB 為準
            combined[k] = {
                'read_date': r.get('read_date', k),
                'total_settle': r.get('total_settle', 0),
                'total_budget': r.get('total_budget', 0),
                'items': r.get('items', {}),
                '_source': 'current',
            }
    snaps = sorted(combined.values(), key=lambda s: s['read_date'])
    unsaved = sum(1 for s in snaps if s.get('_source') == 'current')

    if len(snaps) < 2:
        st.info(f"目前有 {len(snaps)} 筆記錄，需至少 2 筆才能顯示趨勢\n\n"
                f"（提示：多上傳幾個不同日期的 KG 一覽表，或儲存此份快照後再上傳新版本即可累積趨勢）")
        return
    if unsaved:
        st.caption(f"📊 共 {len(snaps)} 筆（含 {unsaved} 筆尚未儲存），儲存快照後會永久保留")
    dates = [s['read_date'][:10] for s in snaps]
    totals = [s['total_settle'] for s in snaps]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=totals, mode='lines+markers+text',
        line=dict(color='#1E40AF', width=2.8), marker=dict(size=7),
        text=[fmt(v) for v in totals], textposition='top center', textfont=dict(size=10)))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=30),
        font=dict(family="Microsoft JhengHei"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key=f"trend_total_{dn}")

    sel = st.multiselect("追蹤單項", ORDER, default=['租工','技術工','機具租金'], key=f"tr_{dn}")
    if sel:
        colors = ['#1E40AF','#3B82F6','#60A5FA','#1E3A8A','#2563EB','#93C5FD','#0F172A']
        fig2 = go.Figure()
        for i, n in enumerate(sel):
            vals = [s.get('items', {}).get(n, {}).get('settlement', 0)
                    if isinstance(s.get('items', {}).get(n), dict) else 0 for s in snaps]
            fig2.add_trace(go.Scatter(x=dates, y=vals, mode='lines+markers', name=n,
                line=dict(color=colors[i % len(colors)], width=2)))
        fig2.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=30),
            font=dict(family="Microsoft JhengHei"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig2, use_container_width=True, key=f"trend_items_{dn}")

    # 每期增量
    inc = []
    for i in range(1, len(snaps)):
        diff = snaps[i]['total_settle'] - snaps[i-1]['total_settle']
        inc.append({'日期': snaps[i]['read_date'][:10],
                    '結算總額': fmt(snaps[i]['total_settle']),
                    '增減': f"+{fmt(diff)}" if diff > 0 else fmt(diff)})
    if inc:
        st.markdown("###### 每期增量")
        st.dataframe(pd.DataFrame(inc), use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════
# 造價分析
# ═══════════════════════════════════════════════════════════════════
def page_cost_analysis():
    st.markdown('<div class="crumb">總覽 / 造價分析</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">造價分析</h1>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">上傳 KG 一覽表 · 設定面積 · 產出八大類造價 Excel</div>', unsafe_allow_html=True)
    v14 = _load_v14()
    if not v14:
        st.error("找不到 kg_cost_analysis_v14.py（請放在同一資料夾）"); return
    areas = load_areas()

    # 1. 上傳
    st.markdown("## 匯入 KG 一覽表")
    uploaded = st.file_uploader("拖拉或選擇 .xlsx / .xls（可多選）",
        type=['xlsx','xls'], accept_multiple_files=True, key='v14_up',
        label_visibility='collapsed')

    if not uploaded:
        names = db_get_all_cost_names()
        if names:
            st.markdown("## 最近造價分析")
            for dn in names:
                snaps = db_get_cost_snaps(dn)
                if not snaps: continue
                latest = snaps[-1]
                with st.expander(f"{dn}　·　{latest['read_date'][:10]}　·　結算 {fmt(latest['total_settle'])}"):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    ap = latest.get('area_ping', 0) or 0
                    with c1:
                        st.caption(f"面積 {ap:,.0f} 坪　·　快照 {len(snaps)} 筆")
                        st.caption(f"來源：{latest.get('source_filename', '-')}")
                    with c2:
                        if ap >= 10: st.metric("元/坪", f"{latest['total_settle']/ap:,.0f}")
                    with c3:
                        xb, xf = db_get_cost_excel(latest['id'])
                        if xb:
                            st.download_button("下載 Excel", data=xb, file_name=xf,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"hd_{latest['id']}", use_container_width=True)
        else:
            st.info("上傳 .xlsx / .xls 後即可自動分析並產出 Excel")
        return

    # 儲存上傳檔
    fp_list = []
    for uf in uploaded:
        tmp = DATA_DIR / uf.name
        with open(tmp, 'wb') as f: f.write(uf.getbuffer())
        fp_list.append(str(tmp))

    h = str(sorted(fp_list))
    if st.session_state.get('_v14_hash') != h:
        infos = []
        with st.spinner("解析 KG 一覽表..."):
            for fp in fp_list:
                try:
                    proj = v14.read_kg_file(fp)
                    raw_pn = proj.get('project_name', '') or ''
                    dn = (clean_project_name(raw_pn)
                          or extract_name_from_filename(fp)
                          or extract_display_name(fp))
                    # 讀 B3 截止日（與假設工程同一邏輯）
                    try:
                        raw = read_xlsx_via_xml(fp)
                        _, cutoff = get_project_info(raw)
                    except Exception:
                        cutoff = ''
                    # 日期優先：① B3 截止日 → ② 檔名 → ③ 今天（完全不依賴檔名順序）
                    file_date = (_parse_date_str(cutoff)
                                 or _parse_date_str(os.path.basename(fp))
                                 or datetime.now().strftime('%Y-%m-%d'))
                    infos.append({'path':fp, 'dn':dn, 'file_date':file_date,
                                  'proj':proj, 'filename':os.path.basename(fp)})
                except Exception as e:
                    st.error(f"{os.path.basename(fp)}: {e}")
        st.session_state['v14_parsed'] = infos
        st.session_state['_v14_hash'] = h
        st.session_state.pop('v14_results', None)

    infos = st.session_state.get('v14_parsed', [])
    if not infos: return

    # 顯示識別結果：依專案名稱分組（名稱與日期皆來自檔案內容）
    from collections import defaultdict
    proj_dates_v14 = defaultdict(list)
    for pi in infos:
        proj_dates_v14[pi['dn']].append(pi['file_date'])
    lines_v14 = []
    for dn, dates in proj_dates_v14.items():
        date_str = " → ".join(sorted(dates))
        tag = "📈 可畫趨勢" if len(dates) >= 2 else "　單點"
        lines_v14.append(f"{tag}　**{dn}**　{date_str}")
    st.info("識別結果（名稱來自檔案 B2，日期來自 B3 截止日）：\n\n" + "\n\n".join(lines_v14))

    # 2. 面積 + 專案類型（依 dn 去重，同專案多日期只顯示一組輸入）
    st.markdown("## 設定面積與專案類型")
    unique_dns = list(dict.fromkeys(pi['dn'] for pi in infos))
    n = min(len(unique_dns), 4)
    cols = st.columns(n if n >= 2 else 1)
    a_inputs = {}; v14_types = {}; v14_conds = {}
    for i, dn in enumerate(unique_dns):
        with cols[i % len(cols)]:
            a_inputs[dn] = area_input(dn, areas, 'v14')
            guessed = detect_project_type(dn)
            idx = PROJECT_TYPES.index(guessed) if guessed in PROJECT_TYPES else len(PROJECT_TYPES) - 1
            v14_types[dn] = st.selectbox("專案類型", PROJECT_TYPES, index=idx, key=f"v14_type_{dn}")
            v14_conds[dn] = render_conditions_input(dn, 'v14_cond')
            h_snaps = db_get_cost_snaps(dn)
            if h_snaps:
                last = h_snaps[-1]
                st.caption(f"歷史 {len(h_snaps)} 筆　·　上次 {fmt(last['total_settle'])}")
    v14_conds = render_conditions_section(unique_dns, v14_conds, 'v14_cond')
    for dn, ap in a_inputs.items():
        sync_area(dn, ap, areas)

    # 3. 產出
    sc1, sc2 = st.columns([4, 1])
    with sc1: st.markdown("## 產出造價分析 Excel")
    with sc2:
        st.write("")
        run = st.button("開始分析", use_container_width=True, type="primary", key='v14_go')

    if run:
        results = []
        with st.spinner("計算中..."):
            for pi in infos:
                dn = pi['dn']; proj = pi['proj']
                ping = a_inputs.get(dn) or areas.get(dn, 0)
                m2 = ping / PING_PER_M2 if ping > 0 else 0
                try:
                    clf = v14.classify_project(proj)
                    sb = proj['settlement']
                    t = sb['total'] if sb['total'] > 0 else clf['gi']
                    import openpyxl as oxl
                    wb = oxl.Workbook(); wb.remove(wb.active)
                    sf = v14.safe_filename(dn) or 'output'
                    v14.write_cost_analysis(wb, proj, clf, m2, f'{sf}_造價'[:31])
                    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
                    xb = buf.getvalue()
                    file_date = pi.get('file_date', datetime.now().strftime('%Y-%m-%d'))
                    xf = f"{sf}_{file_date.replace('-','')}.xlsx"

                    big_sum = {}
                    items_list = []
                    for it in clf['items']:
                        if it['mode'] == 'sub_header': continue
                        big_sum[it['big']] = big_sum.get(it['big'], 0) + it['total']
                        items_list.append({'big':it['big'],'sub':it['sub'],'name':it['name'],
                                           'total':it['total'],'qty':it.get('qty',0),
                                           'unit':it.get('unit','')})

                    if db_check_duplicate('cost_snapshots', dn, file_date):
                        st.warning(f"**{dn}** 日期 {file_date} 已存在，略過")
                    else:
                        pt = v14_types.get(dn, '其他')
                        cd = v14_conds.get(dn, {})
                        db_insert_cost(dn, proj.get('project_name', ''), ping, m2, t,
                                       big_sum, items_list, len(clf.get('unassigned', {})),
                                       pi['filename'], xb, xf, file_date=file_date, project_type=pt, conditions=cd)
                    results.append({'dn':dn,'total':t,'ping':ping,'m2':m2,
                                    'big_groups':big_sum,'items':items_list,
                                    'excel_bytes':xb,'filename':xf,
                                    'unassigned':len(clf.get('unassigned', {}))})
                except Exception as e:
                    st.error(f"{dn}: {e}")
                    import traceback; st.code(traceback.format_exc())
        st.session_state['v14_results'] = results
        st.toast(f"已產出 {len(results)} 份造價分析", icon='✅')

    if 'v14_results' in st.session_state:
        results = st.session_state['v14_results']
        st.markdown("## 分析結果")
        for r in results: _render_cost_result(r)


def _render_cost_result(r):
    prev_snaps = db_get_cost_snaps(r['dn'])
    prev = prev_snaps[-2] if len(prev_snaps) >= 2 else None

    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    with c1:
        delta = None
        if prev:
            diff = r['total'] - prev.get('total_settle', 0)
            delta = f"{'+' if diff > 0 else ''}{fmt(diff)}"
        st.metric(r['dn'], fmt(r['total']), delta)
    with c2:
        if r['ping'] >= 10: st.metric("元/坪", f"{r['total']/r['ping']:,.0f}")
        else: st.metric("元/坪", "—")
    with c3:
        if r['unassigned']: st.metric("未歸類", f"{r['unassigned']} 項")
        else: st.metric("分類", "全數歸類")
    with c4:
        st.write("")
        st.download_button(f"下載 {r['filename']}",
            data=r['excel_bytes'], file_name=r['filename'],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_{r['dn']}", use_container_width=True)

    # 八大類對比或摘要
    if prev:
        prev_big = prev.get('big_groups', {})
        rows = []
        for b in r['big_groups']:
            cur_v = r['big_groups'].get(b, 0); prev_v = prev_big.get(b, 0)
            rows.append({'大類':b, '本次':fmt(cur_v),
                         '上次':fmt(prev_v) if prev_v else '-',
                         '增減':f"{'+' if cur_v-prev_v > 0 else ''}{fmt(cur_v-prev_v)}" if prev_v else '新增'})
        with st.expander(f"{r['dn']} 八大類對比"):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        rows = [{'大類':b, '結算':fmt(v),
                 '佔比':f"{v/r['total']*100:.1f}%" if r['total'] else '-'}
                for b, v in sorted(r['big_groups'].items(), key=lambda x:x[1], reverse=True) if v > 0]
        with st.expander(f"{r['dn']} 八大類摘要"):
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown("---")

# ═══════════════════════════════════════════════════════════════════
# 歷史記錄
# ═══════════════════════════════════════════════════════════════════
def page_history():
    st.markdown('<div class="crumb">總覽 / 歷史記錄</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">歷史記錄</h1>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">所有過往快照（SQLite）· 下載 Excel · 趨勢圖</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["假設工程", "造價分析"])
    with tab1: _history_assumption()
    with tab2: _history_cost()


def _confirm_delete(table, sid, label, rerun_key):
    """兩段式刪除：第一次點設定 pending，第二次點確認"""
    pkey = f"confirm_{table}_{sid}"
    if st.session_state.get(pkey):
        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("確認刪除", type='primary', key=f"ok_{table}_{sid}", use_container_width=True):
                db_delete_snapshot(table, sid)
                st.session_state.pop(pkey, None)
                st.toast(f"已刪除 {label}", icon='✅')
                st.rerun()
        with c2:
            if st.button("取消", key=f"cancel_{table}_{sid}", use_container_width=True):
                st.session_state.pop(pkey, None); st.rerun()
    else:
        if st.button("刪除", key=f"del_{table}_{sid}", use_container_width=True):
            st.session_state[pkey] = True; st.rerun()


def _confirm_clear_all(table, label):
    """兩段式一鍵清除所有快照"""
    pkey = f"confirm_clearall_{table}"
    if st.session_state.get(pkey):
        st.error(f"(!) 即將刪除 **所有 {label} 快照**，此動作無法復原")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✖ 確認全部清除", type='primary',
                         key=f"ok_clearall_{table}", use_container_width=True):
                db_clear_all(table)
                st.session_state.pop(pkey, None)
                st.toast(f"已清除所有{label}快照", icon='✅')
                st.rerun()
        with c2:
            if st.button("取消", key=f"cancel_clearall_{table}", use_container_width=True):
                st.session_state.pop(pkey, None); st.rerun()
    else:
        if st.button(f"🗑 一鍵清除全部 {label}",
                     key=f"trigger_clearall_{table}", use_container_width=True):
            st.session_state[pkey] = True; st.rerun()


def _history_assumption():
    names = db_get_all_assumption_names()
    if not names:
        st.info("尚無假設工程分析記錄"); return
    cc1, cc2 = st.columns([4, 1])
    with cc1: sel = st.selectbox("選擇專案", names, key='hist_a_sel')
    with cc2:
        st.write("")
        _confirm_clear_all('assumption_snapshots', '假設工程')
    snaps = db_get_assumption_snaps(sel)
    if not snaps: return
    st.caption(f"共 {len(snaps)} 筆")

    rows = []
    for s in snaps:
        ap = s.get('area_ping', 0) or 0
        rows.append({
            'ID': s['id'], '日期': s['read_date'][:10],
            '截止日': s.get('cutoff_date', '-') or '-',
            '面積(坪)': f"{ap:,.0f}" if ap else '-',
            '預算': fmt(s.get('total_budget', 0)),
            '結算': fmt(s.get('total_settle', 0)),
            '元/坪': fpp(s.get('total_settle', 0), ap),
            '來源': s.get('source_filename', '-'),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if len(snaps) >= 2:
        st.markdown("#### 結算總額趨勢")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[s['read_date'][:10] for s in snaps],
            y=[s['total_settle'] for s in snaps],
            mode='lines+markers+text', line=dict(color='#3b5d7e', width=2.8),
            marker=dict(size=7),
            text=[fmt(s['total_settle']) for s in snaps], textposition='top center'))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=30),
            font=dict(family="Microsoft JhengHei"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("刪除快照"):
        st.caption("選擇要刪除的 ID，兩段式確認（避免誤刪）")
        id_opts = [s['id'] for s in snaps]
        sid = st.selectbox("快照", id_opts, key='del_a_sel',
            format_func=lambda x: f"ID {x}　·　{next(s['read_date'][:10] for s in snaps if s['id']==x)}　·　結算 {fmt(next(s['total_settle'] for s in snaps if s['id']==x))}")
        _confirm_delete('assumption_snapshots', sid, f"ID {sid}", 'hist_a')


def _history_cost():
    names = db_get_all_cost_names()
    if not names:
        st.info("尚無造價分析記錄"); return
    cc1, cc2 = st.columns([4, 1])
    with cc1: sel = st.selectbox("選擇專案", names, key='hist_c_sel')
    with cc2:
        st.write("")
        _confirm_clear_all('cost_snapshots', '造價分析')
    snaps = db_get_cost_snaps(sel)
    if not snaps: return
    st.caption(f"共 {len(snaps)} 筆")

    if len(snaps) >= 2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[s['read_date'][:10] for s in snaps],
            y=[s['total_settle'] for s in snaps],
            mode='lines+markers+text', line=dict(color='#2c4560', width=2.8),
            marker=dict(size=7),
            text=[fmt(s['total_settle']) for s in snaps], textposition='top center'))
        fig.update_layout(height=300, margin=dict(l=10, r=10, t=30, b=30),
            font=dict(family="Microsoft JhengHei"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    for s in snaps:
        ap = s.get('area_ping', 0) or 0
        with st.expander(f"{s['read_date'][:10]}　·　結算 {fmt(s['total_settle'])}　·　ID {s['id']}"):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.caption(f"專案全名：{s.get('project_full', '-') or '-'}")
                st.caption(f"面積：{ap:,.0f} 坪　·　{s.get('area_m2', 0) or 0:,.0f} m²")
                st.caption(f"來源：{s.get('source_filename', '-') or '-'}")
                if s.get('unassigned_count'): st.caption(f"未歸類：{s['unassigned_count']} 項")
            with c2:
                if ap >= 10: st.metric("元/坪", f"{s['total_settle']/ap:,.0f}")
                xb, xf = db_get_cost_excel(s['id'])
                if xb:
                    st.download_button("下載 Excel", data=xb, file_name=xf,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"hc_{s['id']}", use_container_width=True)
            with c3:
                _confirm_delete('cost_snapshots', s['id'], f"ID {s['id']}", 'hist_c')

            big = s.get('big_groups', {})
            if big:
                rows = [{'大類':b, '結算':fmt(v),
                         '佔比':f"{v/s['total_settle']*100:.1f}%" if s['total_settle'] else '-'}
                        for b, v in sorted(big.items(), key=lambda x:x[1], reverse=True) if v > 0]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# 投標預估
# ═══════════════════════════════════════════════════════════════════
import numpy as np

def _regression(points, target_x):
    if len(points) < 2: return None, None, {'n': len(points)}
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    a, b = np.polyfit(x, y, 1)
    y_pred = a * x + b
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    pred = a * target_x + b
    se = np.sqrt(ss_res / (len(points) - 2)) if len(points) > 2 else 0
    return max(pred, 0), r2, {'n': len(points), 'a': a, 'b': b, 'se': se,
                               'x': x.tolist(), 'y': y.tolist()}

def _db_get_by_type(table, pt):
    c = _db(); c.row_factory = sqlite3.Row
    rows = c.execute(f"SELECT * FROM {table} WHERE project_type=? ORDER BY read_date", (pt,)).fetchall()
    c.close()
    out = []
    for r in rows:
        d = dict(r)
        if 'items_json' in d: d['items'] = json.loads(d.get('items_json') or '{}')
        if 'big_groups_json' in d: d['big_groups'] = json.loads(d.get('big_groups_json') or '{}')
        d['conditions'] = json.loads(d.get('conditions_json') or '{}')
        out.append(d)
    return out

def _db_get_type_counts():
    c = _db()
    rows_a = c.execute("SELECT project_type, COUNT(*) as cnt FROM assumption_snapshots GROUP BY project_type").fetchall()
    rows_c = c.execute("SELECT project_type, COUNT(*) as cnt FROM cost_snapshots GROUP BY project_type").fetchall()
    c.close()
    a = {r[0]: r[1] for r in rows_a}
    cc = {r[0]: r[1] for r in rows_c}
    return a, cc

def _db_delete_snapshot(table, snap_id):
    """刪除指定快照"""
    c = _db()
    c.execute(f"DELETE FROM {table} WHERE id=?", (snap_id,))
    c.commit(); c.close()


def _render_data_manager(sel_type, cost_snaps, assum_snaps):
    """顯示歷史資料管理面板，讓使用者排除或刪除不需要的快照"""
    if not cost_snaps and not assum_snaps:
        return cost_snaps, assum_snaps

    with st.expander("管理歷史資料（排除 / 刪除不需要的專案）", expanded=False):
        st.caption("取消勾選可暫時排除該筆資料不參與回歸；點「刪除」可永久移除。沒有面積的專案已標記提醒。")

        filtered_cost = list(cost_snaps)
        filtered_assum = list(assum_snaps)

        if cost_snaps:
            st.markdown("#### 造價分析資料")
            to_delete_cost = []
            exclude_cost = []
            for i, s in enumerate(cost_snaps):
                ap = s.get('area_ping', 0) or 0
                dn = s.get('display_name', '')
                date = s.get('read_date', '')[:10]
                settle = s.get('total_settle', 0)
                no_area = ap < 10
                warn = "  **(!) 無面積**" if no_area else ""
                label = f"{dn} | {date} | 面積 {ap:,.0f} 坪 | 結算 {fmt(settle)}{warn}"

                col1, col2 = st.columns([9, 1])
                with col1:
                    checked = st.checkbox(label, value=not no_area,
                                          key=f"pred_inc_cost_{sel_type}_{i}")
                with col2:
                    if st.button("刪除", key=f"pred_del_cost_{sel_type}_{i}",
                                 type="secondary"):
                        to_delete_cost.append(s)

                if not checked:
                    exclude_cost.append(i)

            # 處理刪除
            for s in to_delete_cost:
                _db_delete_snapshot('cost_snapshots', s['id'])
                st.toast(f"已刪除：{s.get('display_name', '')} ({s.get('read_date', '')[:10]})")
            if to_delete_cost:
                st.rerun()

            filtered_cost = [s for i, s in enumerate(cost_snaps) if i not in exclude_cost]
            n_excluded = len(exclude_cost)
            if n_excluded:
                st.caption(f"已排除 {n_excluded} 筆，剩餘 {len(filtered_cost)} 筆參與回歸")

        if assum_snaps:
            st.markdown("#### 假設工程資料")
            to_delete_assum = []
            exclude_assum = []
            for i, s in enumerate(assum_snaps):
                ap = s.get('area_ping', 0) or 0
                dn = s.get('display_name', '')
                date = s.get('read_date', '')[:10]
                settle = s.get('total_settle', 0)
                no_area = ap < 10
                warn = "  **(!) 無面積**" if no_area else ""
                label = f"{dn} | {date} | 面積 {ap:,.0f} 坪 | 結算 {fmt(settle)}{warn}"

                col1, col2 = st.columns([9, 1])
                with col1:
                    checked = st.checkbox(label, value=not no_area,
                                          key=f"pred_inc_assum_{sel_type}_{i}")
                with col2:
                    if st.button("刪除", key=f"pred_del_assum_{sel_type}_{i}",
                                 type="secondary"):
                        to_delete_assum.append(s)

                if not checked:
                    exclude_assum.append(i)

            for s in to_delete_assum:
                _db_delete_snapshot('assumption_snapshots', s['id'])
                st.toast(f"已刪除：{s.get('display_name', '')} ({s.get('read_date', '')[:10]})")
            if to_delete_assum:
                st.rerun()

            filtered_assum = [s for i, s in enumerate(assum_snaps) if i not in exclude_assum]
            n_excluded = len(exclude_assum)
            if n_excluded:
                st.caption(f"已排除 {n_excluded} 筆，剩餘 {len(filtered_assum)} 筆參與回歸")

    return filtered_cost, filtered_assum


def _render_r2_guide():
    """R² 決定係數的公式說明與判讀建議面板"""
    with st.expander("R² 決定係數 — 公式說明與判讀建議", expanded=False):
        st.markdown("""
<div style="
    background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
    border: 1px solid var(--border); border-radius: var(--radius-lg);
    padding: 28px 30px; margin-bottom: 8px;
">

<div style="font-weight:700; font-size:1.05rem; color:var(--primary); margin-bottom:14px;">
    <span class="section-dot"></span>什麼是 R²（決定係數）？
</div>

<div style="color:var(--text); font-size:.9rem; line-height:1.8; margin-bottom:18px;">
    R² 衡量<b>回歸模型對資料的解釋力</b> — 面積與造價之間的線性關係強度。<br>
    數值介於 0 ~ 1 之間，<b>越接近 1 表示用面積預估造價越準確</b>。
</div>

<div style="
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 20px 24px; margin-bottom:20px; font-family: var(--mono); font-size:.88rem;
    text-align: center; line-height: 2.2;
">
    <div style="font-weight:600; color:var(--primary); font-size:.82rem; letter-spacing:1px; margin-bottom:6px;">公　式</div>
    <div style="font-size:1.1rem;">
        R² = 1 &minus;
        <span style="display:inline-block; text-align:center; vertical-align:middle;">
            <span style="display:block; border-bottom:2px solid var(--text); padding-bottom:2px;">SS<sub>res</sub></span>
            <span style="display:block; padding-top:2px;">SS<sub>tot</sub></span>
        </span>
    </div>
    <div style="font-size:.78rem; color:var(--muted); margin-top:10px; text-align:left; font-family:inherit;">
        <b>SS<sub>tot</sub></b>（總變異）= &Sigma;(y<sub>i</sub> &minus; ȳ)² → 每個實際造價與<b>平均值</b>的差距平方和<br>
        <b>SS<sub>res</sub></b>（殘差變異）= &Sigma;(y<sub>i</sub> &minus; ŷ<sub>i</sub>)² → 每個實際造價與<b>回歸預測值</b>的差距平方和
    </div>
</div>

<div style="font-weight:700; font-size:1.05rem; color:var(--primary); margin-bottom:12px;">
    <span class="section-dot"></span>判讀建議
</div>

<table style="width:100%; border-collapse:collapse; font-size:.88rem; border-radius:var(--radius); overflow:hidden;">
    <thead>
        <tr style="background:linear-gradient(180deg,#F8FAFC,var(--header-bg));">
            <th style="padding:12px 16px; text-align:left; font-weight:600; color:var(--primary); border-bottom:2px solid var(--border);">R² 範圍</th>
            <th style="padding:12px 16px; text-align:left; font-weight:600; color:var(--primary); border-bottom:2px solid var(--border);">信心等級</th>
            <th style="padding:12px 16px; text-align:left; font-weight:600; color:var(--primary); border-bottom:2px solid var(--border);">投標建議</th>
        </tr>
    </thead>
    <tbody>
        <tr style="border-bottom:1px solid #F1F5F9;">
            <td style="padding:10px 16px;"><span class="pill" style="background:#D1FAE5;color:#065F46;">0.90 以上</span></td>
            <td style="padding:10px 16px; font-weight:600; color:#065F46;">極好</td>
            <td style="padding:10px 16px; color:var(--text);">預估值可信度高，可直接作為投標依據</td>
        </tr>
        <tr style="border-bottom:1px solid #F1F5F9;">
            <td style="padding:10px 16px;"><span class="pill" style="background:#DBEAFE;color:#1E40AF;">0.70 – 0.90</span></td>
            <td style="padding:10px 16px; font-weight:600; color:#1E40AF;">良好</td>
            <td style="padding:10px 16px; color:var(--text);">有參考價值，建議搭配工程經驗判斷</td>
        </tr>
        <tr style="border-bottom:1px solid #F1F5F9;">
            <td style="padding:10px 16px;"><span class="pill" style="background:var(--amber-light);color:var(--amber);">0.50 – 0.70</span></td>
            <td style="padding:10px 16px; font-weight:600; color:var(--amber);">普通</td>
            <td style="padding:10px 16px; color:var(--text);">僅供粗估參考，建議加大安全係數</td>
        </tr>
        <tr>
            <td style="padding:10px 16px;"><span class="pill" style="background:#FEE2E2;color:#DC2626;">0.50 以下</span></td>
            <td style="padding:10px 16px; font-weight:600; color:#DC2626;">不佳</td>
            <td style="padding:10px 16px; color:var(--text);">資料過於分散，建議增加同類型案例後再判斷</td>
        </tr>
    </tbody>
</table>

<div style="
    margin-top:16px; padding:12px 16px; border-radius:8px;
    background:var(--amber-light); border-left:4px solid var(--amber);
    font-size:.82rem; color:#92400E; line-height:1.6;
">
    <b>注意：</b>資料量少（2~3 筆）時 R² 容易偏高（2 點必定 R²=1.0），不代表預估準確。
    隨著歷史案例累積，R² 才更具統計意義。建議至少 5 筆以上再做正式參考。
</div>

</div>
""", unsafe_allow_html=True)


def page_prediction():
    st.markdown('<div class="crumb">總覽 / 投標預估</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="page-title">投標預估</h1>', unsafe_allow_html=True)
    st.markdown('<div class="page-sub">依專案類型 + 樓地板面積，回歸預估工程造價</div>', unsafe_allow_html=True)

    a_counts, c_counts = _db_get_type_counts()
    all_types = sorted(set(list(a_counts.keys()) + list(c_counts.keys()) + PROJECT_TYPES))
    if '其他' in all_types:
        all_types.remove('其他'); all_types.append('其他')

    type_labels = [f"{t}（假設 {a_counts.get(t,0)} 筆 / 造價 {c_counts.get(t,0)} 筆）" for t in all_types]
    if not any(a_counts.get(t,0) + c_counts.get(t,0) > 0 for t in all_types):
        st.info("尚無任何已分類的歷史資料。請先至「假設工程分析」或「造價分析」匯入並儲存快照（需標記專案類型）。")
        return

    st.markdown("## 選擇條件")
    c1, c2 = st.columns(2)
    with c1:
        sel_idx = st.selectbox("專案類型", range(len(all_types)),
                               format_func=lambda i: type_labels[i], key='pred_type')
        sel_type = all_types[sel_idx]
    with c2:
        kp = 'pred_area_ping'; km = 'pred_area_m2'
        if kp not in st.session_state: st.session_state[kp] = 0.0; st.session_state[km] = 0.0
        def _sp(): st.session_state[km] = round(st.session_state[kp] * M2_PER_PING, 0)
        def _sm(): st.session_state[kp] = round(st.session_state[km] * PING_PER_M2, 0)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.number_input("目標面積（坪）", min_value=0.0, step=100.0, key=kp,
                            format="%.0f", on_change=_sp)
        with cc2:
            st.number_input("目標面積（m²）", min_value=0.0, step=100.0, key=km,
                            format="%.0f", on_change=_sm)
    target_ping = float(st.session_state[kp])
    target_m2 = float(st.session_state[km])
    if target_ping > 0 or target_m2 > 0:
        st.caption(f"{target_ping:,.0f} 坪　≈　{target_m2:,.0f} m²")

    # 資料管理：排除 / 刪除快照
    cost_snaps_raw = _db_get_by_type('cost_snapshots', sel_type)
    assum_snaps_raw = _db_get_by_type('assumption_snapshots', sel_type)
    cost_snaps, assum_snaps = _render_data_manager(sel_type, cost_snaps_raw, assum_snaps_raw)

    if target_ping < 10:
        st.info("請輸入目標面積後，系統將自動產出預估結果。")
        _render_r2_guide()
        _render_historical_overview(sel_type)
        return

    # 造價預估
    st.markdown("## 造價預估結果")
    cost_pts = [(s['area_ping'], s['total_settle']) for s in cost_snaps if s.get('area_ping', 0) >= 10]
    if len(cost_pts) >= 2:
        pred_cost, r2, info = _regression(cost_pts, target_ping)
        _render_prediction_result("工程造價", pred_cost, r2, info, target_ping,
                                  cost_snaps, 'cost')
    elif len(cost_pts) == 1:
        pp = cost_pts[0][1] / cost_pts[0][0]
        pred_cost = pp * target_ping
        st.warning(f"僅 1 筆造價資料，以元/坪直接推估（{pp:,.0f} 元/坪）")
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("預估造價", fmt(pred_cost))
        with c2: st.metric("預估元/坪", f"{pp:,.0f}")
        with c3: st.metric("資料量", "1 筆（僅供參考）")
    else:
        st.warning(f"此類型無造價分析資料，無法預估。")

    # 八大類分佈預估
    if cost_snaps:
        _render_breakdown_prediction(cost_snaps, pred_cost if len(cost_pts) >= 1 else 0, target_ping)

    # 假設工程預估
    st.markdown("## 假設工程預估")
    assum_pts = [(s['area_ping'], s['total_settle']) for s in assum_snaps if s.get('area_ping', 0) >= 10]
    if len(assum_pts) >= 2:
        pred_a, r2_a, info_a = _regression(assum_pts, target_ping)
        _render_prediction_result("假設工程", pred_a, r2_a, info_a, target_ping,
                                  assum_snaps, 'assumption')
        _render_assumption_breakdown(assum_snaps, pred_a, target_ping)
    elif len(assum_pts) == 1:
        pp = assum_pts[0][1] / assum_pts[0][0]
        pred_a = pp * target_ping
        st.warning(f"僅 1 筆假設工程資料，以元/坪直接推估（{pp:,.0f} 元/坪）")
        c1, c2 = st.columns(2)
        with c1: st.metric("預估假設工程", fmt(pred_a))
        with c2: st.metric("元/坪", f"{pp:,.0f}")
    else:
        st.info("此類型無假設工程資料。")

    # R² 判讀指南
    _render_r2_guide()

    # 歷史專案列表
    _render_historical_overview(sel_type)


def _render_prediction_result(label, pred, r2, info, target_ping, snaps, kind):
    pp = pred / target_ping if target_ping > 0 else 0
    n = info['n']
    confidence = "充足" if n >= 5 else ("尚可" if n >= 3 else "有限")
    # R² 判讀
    if r2 is not None:
        if r2 >= 0.90:   r2_label, r2_color = "極好", "#065F46"
        elif r2 >= 0.70: r2_label, r2_color = "良好", "#1E40AF"
        elif r2 >= 0.50: r2_label, r2_color = "普通", "#D97706"
        else:            r2_label, r2_color = "不佳", "#DC2626"
    else:
        r2_label, r2_color = "—", "#64748B"
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric(f"預估{label}", fmt(pred))
    with c2: st.metric("預估元/坪", f"{pp:,.0f}")
    with c3:
        st.metric("R²", f"{r2:.3f}" if r2 is not None else "—")
        st.markdown(f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
                    f'background:{r2_color}1A;color:{r2_color};font-size:.76rem;font-weight:600;">'
                    f'{r2_label}</span>', unsafe_allow_html=True)
    with c4: st.metric("資料量", f"{n} 筆（{confidence}）")

    if info.get('se') and n > 2:
        import scipy.stats as stats
        t_val = stats.t.ppf(0.975, n - 2)
        margin = t_val * info['se']
        st.caption(f"95% 信賴區間：{fmt(max(pred - margin, 0))} ~ {fmt(pred + margin)}")

    # 散佈圖 + 回歸線
    fig = go.Figure()
    hist_x = info.get('x', []); hist_y = info.get('y', [])
    names = [s.get('display_name', '') for s in snaps if s.get('area_ping', 0) >= 10]
    fig.add_trace(go.Scatter(x=hist_x, y=hist_y, mode='markers+text',
        marker=dict(size=10, color='#3B82F6'), text=names,
        textposition='top center', textfont=dict(size=9), name='歷史專案'))
    if info.get('a') is not None:
        a, b = info['a'], info['b']
        x_range = [min(hist_x + [target_ping]) * 0.8, max(hist_x + [target_ping]) * 1.2]
        fig.add_trace(go.Scatter(x=x_range, y=[a*x_range[0]+b, a*x_range[1]+b],
            mode='lines', line=dict(color='#94A3B8', dash='dash', width=1.5), name='回歸線'))
    fig.add_trace(go.Scatter(x=[target_ping], y=[pred], mode='markers',
        marker=dict(size=14, color='#EF4444', symbol='star'), name='本次預估'))
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=30),
        font=dict(family="Microsoft JhengHei"), showlegend=True,
        xaxis_title="面積（坪）", yaxis_title="金額",
        legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)


def _render_breakdown_prediction(cost_snaps, pred_total, target_ping):
    valid = [s for s in cost_snaps if s.get('area_ping', 0) >= 10 and s.get('total_settle', 0) > 0]
    if not valid: return
    all_bigs = set()
    for s in valid:
        bg = s.get('big_groups', {})
        if isinstance(bg, str): bg = json.loads(bg)
        all_bigs.update(bg.keys())
    avg_pcts = {}
    for b in all_bigs:
        pcts = []
        for s in valid:
            bg = s.get('big_groups', {})
            if isinstance(bg, str): bg = json.loads(bg)
            t = s['total_settle']
            if t > 0 and b in bg: pcts.append(bg[b] / t)
        avg_pcts[b] = sum(pcts) / len(pcts) if pcts else 0

    with st.expander("八大類預估分佈", expanded=True):
        rows = []
        for b in sorted(avg_pcts.keys()):
            pct = avg_pcts[b]
            est = pred_total * pct if pred_total > 0 else 0
            pp = est / target_ping if target_ping > 0 else 0
            rows.append({'大類': b, '平均佔比': f"{pct*100:.1f}%",
                         '預估金額': fmt(est), '預估元/坪': f"{pp:,.0f}" if pp else '-'})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        fig = go.Figure(data=[go.Pie(
            labels=list(avg_pcts.keys()),
            values=[avg_pcts[b] for b in avg_pcts],
            textinfo='label+percent', hole=0.4)])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
            font=dict(family="Microsoft JhengHei"), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


def _render_assumption_breakdown(assum_snaps, pred_total, target_ping):
    valid = [s for s in assum_snaps if s.get('area_ping', 0) >= 10]
    if not valid: return
    avg_items = {}
    for n in ORDER:
        vals = []
        for s in valid:
            items = s.get('items', {})
            if isinstance(items, str): items = json.loads(items)
            t = s.get('total_settle', 0)
            v = items.get(n, {})
            settle = v.get('settlement', 0) if isinstance(v, dict) else 0
            if t > 0: vals.append(settle / t)
        avg_items[n] = sum(vals) / len(vals) if vals else 0

    with st.expander("13 項假設工程預估明細", expanded=True):
        rows = []
        for n in ORDER:
            pct = avg_items[n]
            est = pred_total * pct if pred_total > 0 else 0
            pp = est / target_ping if target_ping > 0 else 0
            rows.append({'項目': n, '平均佔比': f"{pct*100:.1f}%",
                         '預估金額': fmt(est), '預估元/坪': f"{pp:,.0f}" if pp else '-'})
        total_est = sum(pred_total * avg_items[n] for n in ORDER) if pred_total > 0 else 0
        rows.append({'項目': '合計', '平均佔比': '100%',
                     '預估金額': fmt(pred_total),
                     '預估元/坪': f"{pred_total/target_ping:,.0f}" if target_ping > 0 else '-'})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _snap_to_row(s):
    """將快照轉為歷史總覽表的一列（含條件欄位）"""
    ap = s.get('area_ping', 0) or 0
    c = s.get('conditions', {})
    if isinstance(c, str):
        try: c = json.loads(c)
        except: c = {}
    return {
        '廠區': c.get('fab_code', '') or '',
        '專案': s.get('display_name', ''),
        '日期': s.get('read_date', '')[:10],
        '面積(坪)': f"{ap:,.0f}" if ap else '-',
        '結算': fmt(s.get('total_settle', 0)),
        '元/坪': fpp(s.get('total_settle', 0), ap),
        '地區': c.get('region', '') or '',
        '結構': c.get('struct_type', '') or '',
        '發包': c.get('contract_mode', '') or '',
        '帶料': c.get('with_material', '') or '',
        '帶機具': c.get('with_equipment', '') or '',
        '鋼筋(元/噸)': f"{c['rebar_price']:,.0f}" if c.get('rebar_price') else '',
        '備註': c.get('note', '') or '',
    }

def _render_historical_overview(sel_type):
    st.markdown("## 歷史同類專案")
    cost_snaps = _db_get_by_type('cost_snapshots', sel_type)
    assum_snaps = _db_get_by_type('assumption_snapshots', sel_type)
    if not cost_snaps and not assum_snaps:
        st.info(f"尚無「{sel_type}」類型的歷史資料。請至假設工程或造價分析匯入後標記類型。")
        return
    if cost_snaps:
        st.markdown("#### 造價分析")
        rows = [_snap_to_row(s) for s in cost_snaps]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if assum_snaps:
        st.markdown("#### 假設工程")
        rows = [_snap_to_row(s) for s in assum_snaps]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


if __name__ == '__main__':
    main()
