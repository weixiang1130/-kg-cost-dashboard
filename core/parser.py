# -*- coding: utf-8 -*-
"""KG 一覽表 XML 解析引擎（假設工程 13 項）"""
import re
import io
import zipfile
from lxml import etree

NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def _parse_ref(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return m.group(1).upper(), int(m.group(2))


def read_xlsx_via_xml(filepath: str) -> dict:
    """低階 XML 解析 .xlsx，回傳 {(row, col): value} 字典"""
    data = {}
    zf = zipfile.ZipFile(filepath)
    ss = []
    if 'xl/sharedStrings.xml' in zf.namelist():
        root = etree.parse(io.BytesIO(zf.read('xl/sharedStrings.xml')))
        for si in root.findall('.//ns:si', NS):
            ss.append(''.join(t.text for t in si.findall('.//ns:t', NS) if t.text))
    sf = sorted(f for f in zf.namelist() if re.match(r'xl/worksheets/sheet\d+\.xml', f))
    if not sf:
        raise ValueError("找不到工作表")
    root = etree.parse(io.BytesIO(zf.read(sf[0])))
    for row in root.findall('.//ns:row', NS):
        for c in row.findall('ns:c', NS):
            ref = c.get('r'); t = c.get('t')
            v = c.find('ns:v', NS); ie = c.find('ns:is', NS)
            val = None
            if ie is not None:
                val = ''.join(te.text for te in ie.findall('.//ns:t', NS) if te.text)
            elif t == 's' and v is not None and v.text:
                idx = int(v.text)
                if idx < len(ss): val = ss[idx]
            elif v is not None and v.text:
                val = v.text
            if val is not None:
                col, rn = _parse_ref(ref)
                data[(rn, col)] = val
    return data


def _f(v):
    try: return float(v)
    except: return 0.0


def _parent_subs(data, pr, rs):
    b = _f(data.get((pr, 'M'), '0'))
    q = _f(data.get((pr, 'Q'), '0'))
    w = _f(data.get((pr, 'W'), '0'))
    for r in range(pr + 1, pr + 500):
        if r not in rs: continue
        if (r, 'E') in data: break
        if (r, 'S') in data:
            w += _f(data.get((r, 'W'), '0'))
            q += _f(data.get((r, 'Q'), '0'))
    return b, q, w


def _agg_c_code(data, rows, rs, pat):
    parents = [r for r in rows if pat in str(data.get((r, 'C'), ''))]
    bt = qt = wt = 0
    done = set()
    for pr in parents:
        if pr in done: continue
        done.add(pr)
        bt += _f(data.get((pr, 'M'), '0'))
        qt += _f(data.get((pr, 'Q'), '0'))
        wt += _f(data.get((pr, 'W'), '0'))
        for r in range(pr + 1, pr + 500):
            if r in done or r not in rs: continue
            if (r, 'E') in data: break
            if (r, 'S') in data:
                wt += _f(data.get((r, 'W'), '0'))
                qt += _f(data.get((r, 'Q'), '0'))
                done.add(r)
    return bt, qt, wt


def _find_f(data, rows, kw):
    return [r for r in rows if kw in str(data.get((r, 'F'), '')) and (r, 'E') in data]


def extract_categories(data: dict) -> dict:
    """從解析後的 KG 資料抽取 13 項假設工程"""
    rows = sorted({r for r, _ in data.keys()})
    rs = set(rows)
    cats = {}

    for nm, cd in [('租工', 'A.08.01'), ('打石工', 'A.08.02'), ('技術工', 'A.08.03'),
                   ('雜項工程', 'A.08.04'), ('機具租金', 'A.08.05'), ('零星建材', 'A.08.06')]:
        b, q, w = _agg_c_code(data, rows, rs, cd)
        cats[nm] = {'budget': b, 'contract': q, 'settlement': w}

    for nm, kw in [('安衛零星', '安衛零星'), ('雜支一', '雜支一'), ('雜支二', '雜支二')]:
        prs = _find_f(data, rows, kw)
        bt = qt = wt = 0
        for pr in prs:
            b, q, w = _parent_subs(data, pr, rs)
            bt += b; qt += q; wt += w
        cats[nm] = {'budget': bt, 'contract': qt, 'settlement': wt}

    water = [r for r in rows if '水費' in str(data.get((r, 'F'), ''))
             and not any(x in str(data.get((r, 'F'), '')) for x in ('飲水', '排水', '水電'))
             and (r, 'E') in data]
    bt = qt = wt = 0
    for pr in water:
        b, q, w = _parent_subs(data, pr, rs)
        bt += b; qt += q; wt += w
    cats['水費'] = {'budget': bt, 'contract': qt, 'settlement': wt}

    elec = [r for r in rows if re.match(r'^電費', str(data.get((r, 'F'), '')).strip())
            and (r, 'E') in data]
    bt = qt = wt = 0
    for pr in elec:
        b, q, w = _parent_subs(data, pr, rs)
        bt += b; qt += q; wt += w
    cats['電費'] = {'budget': bt, 'contract': qt, 'settlement': wt}

    phone = _find_f(data, rows, '電話費')
    bt = qt = wt = 0
    for pr in phone:
        bt += _f(data.get((pr, 'M'), '0'))
        qt += _f(data.get((pr, 'Q'), '0'))
        wt += _f(data.get((pr, 'W'), '0'))
    cats['電話費'] = {'budget': bt, 'contract': qt, 'settlement': wt}

    sal = _find_f(data, rows, '薪資')
    bt = qt = wt = 0
    for pr in sal:
        b, q, w = _parent_subs(data, pr, rs)
        bt += b; qt += q; wt += w
    cats['人員薪資'] = {'budget': bt, 'contract': qt, 'settlement': wt}

    return cats


def get_project_info(data: dict) -> tuple:
    """回傳 (專案名稱, 截止日)"""
    return data.get((2, 'B'), '未知專案'), data.get((3, 'B'), '')
