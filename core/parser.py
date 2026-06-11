# -*- coding: utf-8 -*-
"""KG 一覽表 XML 解析引擎（假設工程 13 項）"""
import re
import io
import os
import zipfile
from lxml import etree

NS = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def _parse_ref(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return m.group(1).upper(), int(m.group(2))


def _col_letter(idx: int) -> str:
    """0-based 欄索引 → Excel 欄字母（0→A, 26→AA）"""
    s = ''
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(ord('A') + rem) + s
    return s


def _read_xls(filepath: str) -> dict:
    """讀取舊版 .xls（BIFF 格式），回傳與 XML 解析相同的 {(row, col): value} 字典"""
    import xlrd
    xwb = xlrd.open_workbook(filepath)
    xs = xwb.sheet_by_index(0)
    data = {}
    for r in range(xs.nrows):
        for c in range(xs.ncols):
            ct = xs.cell_type(r, c)
            if ct in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                continue
            v = xs.cell_value(r, c)
            if ct == xlrd.XL_CELL_DATE:
                try:
                    v = xlrd.xldate_as_datetime(v, xwb.datemode).strftime('%Y/%m/%d')
                except Exception:
                    pass
            data[(r + 1, _col_letter(c))] = v
    xwb.release_resources()
    return data


def _col_to_idx(c: str) -> int:
    """欄字母 → 1-based 索引（A→1, AA→27）"""
    i = 0
    for ch in c:
        i = i * 26 + (ord(ch) - ord('A') + 1)
    return i


def normalize_kg_layout(data: dict) -> dict:
    """偵測 KG 檔欄位配置；舊版匯出（如 2022 年版：發包契約在 M、結算在 Y）
    自動將欄位搬到標準位置，讓下游 parser（寫死 W/AE/U/J/S 等欄）通用。
    標準版（發包契約=R、結算完工成本=AD）原樣返回，零影響。
    """
    rows = sorted({r for r, _ in data.keys()})
    if not rows:
        return data
    # 找 header 列（「專案任務」在 A 欄）
    hr = None
    for r in rows[:10]:
        if str(data.get((r, 'A'), '') or '').strip() == '專案任務':
            hr = r
            break
    if hr is None:
        return data
    sub = hr + 1

    def find_label(label):
        for c in {c for (r, c) in data.keys() if r == hr}:
            if label in str(data.get((hr, c), '') or ''):
                return c
        return None

    ctr = find_label('發包契約')
    stl = find_label('結算完工成本')
    if not ctr or not stl:
        return data
    if ctr == 'R' and stl == 'AD':
        return data  # 標準版

    def find_sub(start_col, label, span=12):
        si = _col_to_idx(start_col)
        for off in range(span):
            c = _col_letter(si + off - 1)
            if str(data.get((sub, c), '') or '').strip() == label:
                return c
        return None

    # 舊版 → 標準欄位映射（一個來源欄可對多個目標欄）
    mapping = {}  # old_col → [std_cols]

    def add(old, *new):
        if old:
            mapping.setdefault(old, []).extend(new)

    bud = find_label('預算')
    if bud:
        add(find_sub(bud, '複價'), 'M', 'Q')   # 預算複價 → 原始預算金額 + 預算複價
    add(find_sub(ctr, '數量'), 'U')            # 發包數量
    add(find_sub(ctr, '複價'), 'W')            # 發包複價（現行結算基準欄）
    add(find_sub(ctr, '合約項目名稱') or find_sub(ctr, '合約項目名稱', 15), 'S')
    add(find_sub(stl, '數量'), 'AD')           # 結算數量
    add(find_sub(stl, '複價'), 'AE')           # 結算複價
    add(find_label('單位'), 'J')               # 單位
    if not mapping:
        return data

    src_cols = set(mapping.keys())
    dst_cols = {d for ds in mapping.values() for d in ds}
    # 來源=目標的（已在正確位置）不用搬
    if all(len(ds) == 1 and old == ds[0] for old, ds in mapping.items()):
        return data

    out = {}
    for (r, c), v in data.items():
        if r <= sub:
            out[(r, c)] = v          # header 列保留原樣
            continue
        if c in src_cols or c in dst_cols:
            continue                 # 待重排的欄先清空
        out[(r, c)] = v
    for (r, c), v in data.items():
        if r <= sub:
            continue
        if c in mapping:
            for d in mapping[c]:
                out[(r, d)] = v
    return out


def read_xlsx_via_xml(filepath: str) -> dict:
    """低階 XML 解析 .xlsx，回傳 {(row, col): value} 字典；.xls 走 xlrd
    舊版 KG 匯出格式會自動正規化欄位到標準位置"""
    if os.path.splitext(filepath)[1].lower() == '.xls':
        return normalize_kg_layout(_read_xls(filepath))
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
    return normalize_kg_layout(data)


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


def _label_value(data: dict, keyword: str) -> str:
    """掃描前 5 列：找含 keyword 標籤的儲存格，回傳同列右側第一個非空值
    （舊版匯出的專案名稱可能在 G2 而非 B2）"""
    for r in range(1, 6):
        cols = sorted({c for (rr, c) in data.keys() if rr == r},
                      key=lambda c: (len(c), c))
        for i, c in enumerate(cols):
            if keyword in str(data.get((r, c), '') or ''):
                for c2 in cols[i + 1:]:
                    v = data.get((r, c2))
                    if v is not None and str(v).strip():
                        return str(v).strip()
    return ''


def get_project_info(data: dict) -> tuple:
    """回傳 (專案名稱, 截止日)；標準版在 B2/B3，舊版自動以標籤定位"""
    pname = data.get((2, 'B'), '') or ''
    cutoff = data.get((3, 'B'), '') or ''
    if not str(pname).strip():
        pname = _label_value(data, '專案名稱')
    if not str(cutoff).strip():
        cutoff = _label_value(data, '統計截止日')
    return (pname or '未知專案'), cutoff
