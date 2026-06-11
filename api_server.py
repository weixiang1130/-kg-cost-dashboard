#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 後端 — 成本管理監測系統 REST API
啟動：uvicorn api_server:app --reload --port 8000
"""
import os, io, json, shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import (
    DATA_DIR, DB_FILE, ORDER, PROJECT_TYPES, M2_PER_PING, PING_PER_M2,
    init_db,
    # parser
    read_xlsx_via_xml, extract_categories, get_project_info,
    # conditions
    detect_project_type, detect_fab_code, detect_region, default_conditions,
    # utils
    parse_date_str, extract_file_date, extract_name_from_filename,
    clean_project_name, extract_display_name, fmt, fpp,
    # db
    db_insert_assumption, db_get_assumption_snaps, db_get_all_assumption_names,
    db_insert_cost, db_get_cost_snaps, db_get_all_cost_names,
    db_get_cost_excel, db_update_cost_area, db_update_assumption_area,
    db_delete_snapshot,
    db_clear_all, db_check_duplicate,
    db_get_by_type, db_get_type_counts,
    # areas
    load_areas, save_areas, sync_area,
    # analysis
    regression, render_breakdown_ratios, render_assumption_ratios,
    confidence_label, unit_cost_stats,
    ensemble_predict, STRUCT_FACTORS, load_index, save_index,
    load_prices, save_prices, reference_price, price_delta_pct,
    db_update_conditions,
)
from core.utils import load_v14_module

# ── Init ──
DATA_DIR.mkdir(exist_ok=True)
init_db()

# 暫存 cost_analyze 產生的 Excel bytes，供 save_cost 取用
# key = (display_name, file_date), value = (timestamp, bytes)
_excel_cache: dict[tuple, tuple[float, bytes]] = {}
_CACHE_TTL = 1800  # 30 minutes
_CACHE_MAX = 50    # max entries

def _cache_put(key: tuple, data: bytes):
    """Store Excel bytes with timestamp; evict stale/overflow entries."""
    import time
    now = time.time()
    # Evict expired entries
    expired = [k for k, (ts, _) in _excel_cache.items() if now - ts > _CACHE_TTL]
    for k in expired:
        del _excel_cache[k]
    # Evict oldest if over max
    while len(_excel_cache) >= _CACHE_MAX:
        oldest = min(_excel_cache, key=lambda k: _excel_cache[k][0])
        del _excel_cache[oldest]
    _excel_cache[key] = (now, data)

def _cache_pop(key: tuple) -> bytes | None:
    """Retrieve and remove cached Excel bytes (None if expired/missing)."""
    import time
    entry = _excel_cache.pop(key, None)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL:
        return None
    return data

app = FastAPI(title="KG 成本管理 API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════
class ConditionsIn(BaseModel):
    fab_code: str = ''
    region: str = ''
    struct_type: str = ''
    floors: int = 0
    duration_months: int = 0
    contract_mode: str = ''
    with_material: str = ''
    with_equipment: str = ''
    rebar_price: float = 0
    concrete_price: float = 0
    formwork_price: float = 0
    price_index: float = 0
    note: str = ''


class AssumptionSaveIn(BaseModel):
    display_name: str
    project_full: str = ''
    cutoff_date: str = ''
    area_ping: float = 0
    total_budget: float = 0
    total_settle: float = 0
    items: dict = {}
    source_filename: str = ''
    file_date: str = ''
    project_type: str = '其他'
    conditions: dict = {}


class CostSaveIn(BaseModel):
    display_name: str
    project_full: str = ''
    area_ping: float = 0
    area_m2: float = 0
    total_settle: float = 0
    big_groups: dict = {}
    items: list = []
    unassigned_count: int = 0
    source_filename: str = ''
    excel_filename: str = ''
    file_date: str = ''
    project_type: str = '其他'
    conditions: dict = {}


class AreasIn(BaseModel):
    areas: dict


class BatchSaveIn(BaseModel):
    items: list[dict]


# ═══════════════════════════════════════════════
# Parse KG
# ═══════════════════════════════════════════════
@app.post("/api/parse-kg")
async def parse_kg(files: list[UploadFile] = File(...)):
    """上傳 .xlsx，回傳解析後的假設工程 JSON"""
    results = []
    for uf in files:
        tmp = DATA_DIR / Path(uf.filename).name
        content = await uf.read()
        with open(tmp, 'wb') as f:
            f.write(content)
        try:
            raw = read_xlsx_via_xml(str(tmp))
            proj_name, cutoff = get_project_info(raw)
            cats = extract_categories(raw)
            dn = (clean_project_name(proj_name)
                  or extract_name_from_filename(str(tmp))
                  or extract_display_name(str(tmp)))
            file_date = (parse_date_str(cutoff)
                         or parse_date_str(os.path.basename(uf.filename))
                         or datetime.now().strftime('%Y-%m-%d'))
            items = {k: {'budget': cats[k]['budget'], 'settlement': cats[k]['settlement']}
                     for k in ORDER}
            tb = sum(cats[k]['budget'] for k in ORDER)
            ts = sum(cats[k]['settlement'] for k in ORDER)
            results.append({
                'display_name': dn,
                'project_full': proj_name,
                'cutoff': cutoff,
                'file_date': file_date,
                'filename': uf.filename,
                'total_budget': tb,
                'total_settle': ts,
                'items': items,
                'categories': cats,
                'detected_type': detect_project_type(dn),
                'detected_fab_code': detect_fab_code(dn),
                'detected_region': detect_region(dn),
            })
        except Exception as e:
            results.append({'filename': uf.filename, 'error': str(e)})
    return {'results': results}


# ═══════════════════════════════════════════════
# Projects overview
# ═══════════════════════════════════════════════
@app.get("/api/projects")
def get_projects():
    """所有專案名稱 + 最新快照摘要"""
    a_names = db_get_all_assumption_names()
    c_names = db_get_all_cost_names()
    all_names = sorted(set(a_names) | set(c_names))
    projects = []
    for dn in all_names:
        proj = {'display_name': dn, 'assumption_count': 0, 'cost_count': 0}
        a_snaps = db_get_assumption_snaps(dn)
        if a_snaps:
            proj['assumption_count'] = len(a_snaps)
            last = a_snaps[-1]
            proj['last_assumption'] = {
                'read_date': last['read_date'],
                'total_settle': last.get('total_settle', 0),
                'area_ping': last.get('area_ping', 0),
            }
        c_snaps = db_get_cost_snaps(dn)
        if c_snaps:
            proj['cost_count'] = len(c_snaps)
            last = c_snaps[-1]
            proj['last_cost'] = {
                'read_date': last['read_date'],
                'total_settle': last.get('total_settle', 0),
                'area_ping': last.get('area_ping', 0),
            }
        projects.append(proj)
    return {
        'total_projects': len(all_names),
        'total_assumption_names': len(a_names),
        'total_cost_names': len(c_names),
        'projects': projects,
    }


# ═══════════════════════════════════════════════
# Assumption
# ═══════════════════════════════════════════════
@app.get("/api/assumption/{dn}")
def get_assumption(dn: str):
    snaps = db_get_assumption_snaps(dn)
    return {'display_name': dn, 'count': len(snaps), 'snapshots': snaps}


@app.post("/api/assumption/save")
def save_assumption(data: AssumptionSaveIn):
    rd = data.file_date or datetime.now().strftime('%Y-%m-%d')
    if db_check_duplicate('assumption_snapshots', data.display_name, rd):
        raise HTTPException(400, f"{data.display_name} 日期 {rd} 已存在")
    db_insert_assumption(
        data.display_name, data.project_full, data.cutoff_date,
        data.area_ping, data.total_budget, data.total_settle,
        data.items, data.source_filename,
        file_date=rd, project_type=data.project_type,
        conditions=data.conditions,
    )
    return {'status': 'ok', 'display_name': data.display_name, 'read_date': rd}


@app.put("/api/assumption/{sid}/area")
def update_assumption_area(sid: int, data: dict):
    area_ping = float(data.get('area_ping', 0))
    if area_ping < 0:
        raise HTTPException(400, "面積不能為負數")
    db_update_assumption_area(sid, area_ping)
    # Sync to areas JSON (including clearing to 0)
    try:
        dn = data.get('display_name', '')
        if dn:
            areas = load_areas()
            if area_ping > 0:
                areas[dn] = area_ping
            elif dn in areas:
                del areas[dn]
            save_areas(areas)
    except Exception:
        pass
    return {'status': 'ok', 'area_ping': area_ping}


# ═══════════════════════════════════════════════
# Cost
# ═══════════════════════════════════════════════
def _normalize_big_groups(bg):
    """Normalize old-format big_groups keys to standard 8-group keys.
    Always run the mapping — handles mixed old+new key dicts correctly."""
    if not bg:
        return bg
    result = {}
    for k, v in bg.items():
        new_key = _BIG8_MAP.get(k, k)
        result[new_key] = result.get(new_key, 0) + v
    return result


@app.get("/api/cost/{dn}")
def get_cost(dn: str):
    snaps = db_get_cost_snaps(dn)
    # Normalize big_groups keys for frontend
    for s in snaps:
        s['big_groups'] = _normalize_big_groups(s.get('big_groups', {}))
    return {'display_name': dn, 'count': len(snaps), 'snapshots': snaps}


# 八大類分類映射：v14 CATEGORY_MAP 的 big 欄位 → 八大類標準 key
_BIG8_MAP = {
    '壹、假設工程': '假設工程',
    '貳、基礎工程': '基礎工程',
    '參、結構工程': '結構工程',
    '肆、外牆裝修': '裝修工程', '伍、室內裝修': '裝修工程', '陸、門窗工程': '裝修工程',
    '柒、設備工程': '設備工程',
    '捌': '景觀外構', '玖': '景觀外構',
    '拾': '機電工程',
    '拾壹': '營造管理',
}

def _aggregate_big8(clf_items):
    """將 classify_project items 聚合成八大類"""
    big8 = {}
    for it in clf_items:
        if it['mode'] == 'sub_header':
            continue
        key = _BIG8_MAP.get(it['big'], it['big'])
        big8[key] = big8.get(key, 0) + it['total']
    return big8


def _build_proj_from_xml(data):
    """
    從 XML 解析結果構建 v14 classify_project 所需的 proj dict。
    openpyxl data_only=True 無法讀取 KG 檔案的公式快取值，
    但 XML parser 可以直接讀取，所以改用此函式。
    """
    import re as _re
    from collections import defaultdict

    rows = sorted({r for r, _ in data.keys()})
    cat_totals = defaultdict(float)
    cat_descs = {}
    raw_rows = defaultdict(list)
    conc_subs = defaultdict(lambda: {'qty': 0, 'amt': 0, 'unit': ''})

    # Detect Format-A vs Format-B by scanning header rows for known keywords
    fmt = 'B'
    for hr in rows[:15]:
        header_text = ' '.join(str(data.get((hr, c), '') or '') for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
        if '已估驗結算金額' in header_text or '售服費' in header_text:
            fmt = 'A'
            break

    def _fv(v):
        """安全轉 float — 儲存格可能含文字（如「未完成」）"""
        try: return float(v)
        except (ValueError, TypeError): return 0.0

    # 找結算複價所在欄位：通常在 W 或 AE
    # 先嘗試 W 欄，若全為 0 則嘗試 AE
    settle_col = 'W'
    test_sum = sum(_fv(data.get((r, 'W'), 0)) for r in rows[:200] if data.get((r, 'C')))
    if test_sum == 0:
        settle_col = 'AE'

    # 預算欄位
    budget_col = 'Q'
    test_bud = sum(_fv(data.get((r, 'Q'), 0)) for r in rows[:200] if data.get((r, 'C')))
    if test_bud == 0:
        budget_col = 'AB'

    # Format-A 四分項欄位（已估驗/未施作/人事及規費/售服費的複價欄）
    # 使用 data dict 的實際欄位，涵蓋多字母欄 (AA, AB, AE …)
    ya_col = yb_col = yc_col = yd_col = None
    if fmt == 'A':
        all_data_cols = sorted({c for _, c in data.keys()})
        for hr in rows[:15]:
            for c_letter in all_data_cols:
                v = str(data.get((hr, c_letter), '') or '')
                if '已估驗結算金額' in v: ya_col = c_letter
                elif '未施作預估金額' in v: yb_col = c_letter
                elif '人事及規費' in v: yc_col = c_letter
                elif '售服費' in v: yd_col = c_letter

    total_settle = 0.0
    cur_c = None
    ysum = aasum = acsum = aesum = 0.0  # Format-A 四分項合計
    conc_re = _re.compile(
        r'(kgf|psi|CLSM|PC混凝土|預拌混凝土|預拌SCC|膨脹混凝土|細粒料|犬走|車道植草|高壓混凝土)',
        _re.IGNORECASE
    )
    CONCRETE_CODES = {'C.04.01.00','C.04.05.00','C.04.03.00','C.04.00.00'}

    for r in rows:
        cv = data.get((r, 'C'))
        dv = data.get((r, 'D'), '')
        ev = data.get((r, 'E'), '')     # 工料編碼 (work item code)
        fv = data.get((r, 'F'), '')     # 工料名稱 (work item description)
        jv = data.get((r, 'J'), '')     # 單位
        sa = _fv(data.get((r, settle_col), 0))
        sq = _fv(data.get((r, 'U'), 0)) if settle_col == 'W' else _fv(data.get((r, 'AD'), 0))
        cq = _fv(data.get((r, 'N'), 0))

        # Format-A: accumulate four sub-columns (已估驗/未施作/人事及規費/售服費)
        if fmt == 'A':
            if ya_col: ysum += _fv(data.get((r, ya_col), 0))
            if yb_col: aasum += _fv(data.get((r, yb_col), 0))
            if yc_col: acsum += _fv(data.get((r, yc_col), 0))
            if yd_col: aesum += _fv(data.get((r, yd_col), 0))

        if cv:
            cv = str(cv).strip()
            if _re.match(r'^[A-Z]\.\d', cv):
                cur_c = cv
                if cur_c not in cat_descs and dv:
                    cat_descs[cur_c] = str(dv).strip()

        if cur_c and sa:
            cat_totals[cur_c] += sa
            u = str(jv).strip() if jv else ''
            e = str(fv).strip() if fv else ''  # v14 uses 'code' for description
            raw_rows[cur_c].append({
                'sq': sq, 'sa': sa, 'cq': cq, 'unit': u, 'code': e,
            })

        # 混凝土子項 — 用 column E (工料編碼) split 取子名稱，與 v14 一致
        if cur_c in CONCRETE_CODES and ev and sa:
            ecode = str(ev).strip()
            parts = ecode.split('-', 1)
            sn = parts[1] if len(parts) > 1 else ecode
            if conc_re.search(sn):
                conc_subs[sn]['amt'] += sa
                conc_subs[sn]['qty'] += sq
                if u: conc_subs[sn]['unit'] = u

    # ════════════════════════════════════════════
    # Empty C-code recovery (simplified from v14 Format Normalizer)
    # 偵測空 C-code 行的金額佔比，若 >10% 則啟動描述欄反查修正
    # ════════════════════════════════════════════
    _initial_vsum = sum(cat_totals.values())
    if _initial_vsum > 0:
        strict_total = 0.0
        for r in rows:
            cv = data.get((r, 'C'))
            sa2 = _fv(data.get((r, settle_col), 0))
            if cv and _re.match(r'^[A-Z]\.\d', str(cv).strip()) and sa2:
                strict_total += sa2
        orphan_amt = _initial_vsum - strict_total
        empty_rate = orphan_amt / _initial_vsum * 100

        if empty_rate > 10:
            # Scan all columns for a description column mapping to cat_descs
            all_cols = sorted({c for _, c in data.keys()})
            known_descs = set(cat_descs.values())
            best_col = None
            best_matches = 0

            for tc in all_cols:
                if tc == 'C':
                    continue
                matches = sum(
                    1 for r in rows[:300]
                    if (v := data.get((r, tc))) and isinstance(v, str)
                    and v.strip() in known_descs
                )
                if matches > best_matches:
                    best_matches = matches
                    best_col = tc

            if best_col and best_matches >= 5:
                # Build value→C-code mapping from explicit-C-code rows
                val_to_code: dict[str, str] = {}
                for r in rows:
                    cv = data.get((r, 'C'))
                    sa2 = _fv(data.get((r, settle_col), 0))
                    if not (cv and _re.match(r'^[A-Z]\.\d', str(cv).strip())):
                        continue
                    if not sa2:
                        continue
                    fb = data.get((r, best_col))
                    if fb and isinstance(fb, str) and fb.strip():
                        vk = fb.strip()
                        if vk not in val_to_code:
                            val_to_code[vk] = str(cv).strip()

                # Check coverage on empty-C-code rows
                empty_covered = empty_total = 0
                for r in rows:
                    cv = data.get((r, 'C'))
                    sa2 = _fv(data.get((r, settle_col), 0))
                    if not sa2:
                        continue
                    if cv and _re.match(r'^[A-Z]\.\d', str(cv).strip()):
                        continue
                    empty_total += 1
                    fb = data.get((r, best_col))
                    if fb and isinstance(fb, str) and fb.strip() in val_to_code:
                        empty_covered += 1
                coverage = empty_covered / empty_total * 100 if empty_total else 0

                if coverage > 60:
                    # Rebuild with recovery: description column → C-code fallback
                    cat_totals = defaultdict(float)
                    raw_rows = defaultdict(list)
                    conc_subs = defaultdict(lambda: {'qty': 0, 'amt': 0, 'unit': ''})
                    cur_c = None
                    for r in rows:
                        cv = data.get((r, 'C'))
                        fb = data.get((r, best_col))
                        sa2 = _fv(data.get((r, settle_col), 0))
                        sq2 = (_fv(data.get((r, 'U'), 0)) if settle_col == 'W'
                               else _fv(data.get((r, 'AD'), 0)))
                        cq2 = _fv(data.get((r, 'N'), 0))
                        ev2 = data.get((r, 'E'), '')
                        fv2 = data.get((r, 'F'), '')
                        jv2 = data.get((r, 'J'), '')

                        if cv and _re.match(r'^[A-Z]\.\d', str(cv).strip()):
                            cur_c = str(cv).strip()
                            dv2 = data.get((r, 'D'), '')
                            if cur_c not in cat_descs and dv2:
                                cat_descs[cur_c] = str(dv2).strip()
                        elif fb and isinstance(fb, str) and fb.strip() in val_to_code:
                            cur_c = val_to_code[fb.strip()]
                        # else: inherit cur_c from row above

                        if sa2 and cur_c:
                            cat_totals[cur_c] += sa2
                            u = str(jv2).strip() if jv2 else ''
                            e = str(fv2).strip() if fv2 else ''
                            raw_rows[cur_c].append({
                                'sq': sq2, 'sa': sa2, 'cq': cq2,
                                'unit': u, 'code': e,
                            })
                            if cur_c in CONCRETE_CODES and ev2 and sa2:
                                ecode = str(ev2).strip()
                                parts = ecode.split('-', 1)
                                sn = parts[1] if len(parts) > 1 else ecode
                                if conc_re.search(sn):
                                    conc_subs[sn]['amt'] += sa2
                                    conc_subs[sn]['qty'] += sq2
                                    if u:
                                        conc_subs[sn]['unit'] = u

    vsum = sum(cat_totals.values())
    gt = (ysum + aasum + acsum + aesum) if fmt == 'A' else vsum
    # 若 Format-A 四分項與逐行加總差距過大，回退到逐行加總
    if fmt == 'A' and vsum > 0 and gt > 0:
        if abs(gt - vsum) > max(vsum * 0.01, 10000):
            gt = vsum

    return {
        'project_name': data.get((2, 'B'), ''),
        'cat_totals': dict(cat_totals),
        'cat_descs': cat_descs,
        'raw_rows': dict(raw_rows),
        'concrete_subs': dict(conc_subs),
        'settlement': {'fmt': fmt, 'total': gt, 'V': vsum},
    }


@app.post("/api/cost/analyze")
async def cost_analyze(files: list[UploadFile] = File(...)):
    """上傳檔案，執行造價分析，回傳結果"""
    v14 = load_v14_module()
    if not v14:
        raise HTTPException(500, "找不到 kg_cost_analysis_v14.py")

    results = []
    for uf in files:
        tmp = DATA_DIR / Path(uf.filename).name
        content = await uf.read()
        with open(tmp, 'wb') as f:
            f.write(content)
        try:
            # 使用 XML 解析（openpyxl data_only=True 無法讀取 KG 公式快取值）
            raw = read_xlsx_via_xml(str(tmp))
            proj_name, cutoff = get_project_info(raw)
            proj = _build_proj_from_xml(raw)

            # 舊版匯出的專案名不在 B2，fallback 到 get_project_info 的標籤定位
            raw_pn = (proj.get('project_name') or proj_name or '')
            dn = (clean_project_name(raw_pn)
                  or extract_name_from_filename(str(tmp))
                  or extract_display_name(str(tmp)))
            file_date = (parse_date_str(cutoff)
                         or parse_date_str(os.path.basename(uf.filename))
                         or datetime.now().strftime('%Y-%m-%d'))

            clf = v14.classify_project(proj)
            sb = proj['settlement']
            total = sb['total'] if sb['total'] > 0 else clf['gi']

            big8 = _aggregate_big8(clf['items'])
            items_list = []
            for it in clf['items']:
                if it['mode'] == 'sub_header': continue
                items_list.append({
                    'big': _BIG8_MAP.get(it['big'], it['big']),
                    'sub': it['sub'], 'name': it['name'],
                    'total': it['total'], 'qty': it.get('qty', 0), 'unit': it.get('unit', ''),
                })

            # Generate Excel and cache bytes for save_cost
            excel_filename = ''
            try:
                import openpyxl as oxl
                wb = oxl.Workbook(); wb.remove(wb.active)
                sf = v14.safe_filename(dn) or 'output'
                # 取已登錄面積（坪→m²），讓 Excel 的元/坪、元/m²、權比欄有值
                area_m2 = _match_area(dn, load_areas()) * M2_PER_PING
                v14.write_cost_analysis(wb, proj, clf, area_m2, f'{sf}_造價'[:31])
                buf = io.BytesIO(); wb.save(buf); buf.seek(0)
                excel_filename = f"{sf}_{file_date.replace('-','')}.xlsx"
                _cache_put((dn, file_date), buf.getvalue())
            except Exception:
                pass

            results.append({
                'display_name': dn,
                'file_date': file_date,
                'filename': uf.filename,
                'total_settle': total,
                'big_groups': big8,
                'items': items_list,
                'unassigned_count': len(clf.get('unassigned', {})),
                'detected_type': detect_project_type(dn),
                'excel_filename': excel_filename,
            })
        except Exception as e:
            results.append({'filename': uf.filename, 'error': str(e)})
    return {'results': results}


@app.post("/api/cost/save")
def save_cost(data: CostSaveIn):
    rd = data.file_date or datetime.now().strftime('%Y-%m-%d')
    if db_check_duplicate('cost_snapshots', data.display_name, rd):
        raise HTTPException(400, f"{data.display_name} 日期 {rd} 已存在")
    am = data.area_ping / 0.3025 if data.area_ping > 0 else data.area_m2
    # Retrieve cached Excel bytes from cost_analyze
    cache_key = (data.display_name, rd)
    xb = _cache_pop(cache_key)
    db_insert_cost(
        data.display_name, data.project_full, data.area_ping, am,
        data.total_settle, data.big_groups, data.items,
        data.unassigned_count, data.source_filename,
        xb, data.excel_filename,
        file_date=rd, project_type=data.project_type,
        conditions=data.conditions,
    )
    return {'status': 'ok', 'display_name': data.display_name, 'read_date': rd}


@app.put("/api/cost/{sid}/area")
def update_cost_area(sid: int, data: dict):
    """更新某個造價快照的面積"""
    area_ping = float(data.get('area_ping', 0))
    if area_ping < 0:
        raise HTTPException(400, "面積不能為負數")
    db_update_cost_area(sid, area_ping)
    # Sync to areas JSON (including clearing to 0)
    try:
        dn = data.get('display_name', '')
        if dn:
            areas = load_areas()
            if area_ping > 0:
                areas[dn] = area_ping
            elif dn in areas:
                del areas[dn]
            save_areas(areas)
    except Exception:
        pass
    return {'status': 'ok', 'area_ping': area_ping,
            'area_m2': round(area_ping / 0.3025) if area_ping > 0 else 0}


@app.get("/api/cost/excel/{sid}")
def download_cost_excel(sid: int):
    xb, xf = db_get_cost_excel(sid)
    if not xb:
        raise HTTPException(404, "Excel 不存在")
    return Response(
        content=xb,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={xf}"},
    )


# ═══════════════════════════════════════════════
# Prediction
# ═══════════════════════════════════════════════
@app.get("/api/prediction")
def get_prediction(
    project_type: str = Query(...),
    area_ping: float = Query(..., ge=10),
    struct_type: str = Query(''),       # RC / SC / SRC
    contract_mode: str = Query(''),     # 總價承攬 / 實作實算 / 成本加酬金
    with_material: str = Query(''),     # 無 / 鋼筋 / 鋼構 / 其他
    escalate: bool = Query(True),       # 是否做物價指數調整
    rebar_price: float = Query(0),      # 目前鋼筋發包價 元/噸（0=未輸入）
    concrete_price: float = Query(0),   # 目前混凝土價 元/m³（0=未輸入）
    labor: float = Query(0),            # 工資行情偏差 %（無單一市價，維持指數）
    rebar: float = Query(0),            # （相容舊版）鋼筋指數 %
    concrete: float = Query(0),         # （相容舊版）混凝土指數 %
):
    """投標預估 — 三法三角驗證（時間調整單價法 / 回歸法 / 分項組合法）"""
    cost_snaps = db_get_by_type('cost_snapshots', project_type)
    assum_snaps = db_get_by_type('assumption_snapshots', project_type)

    target_conds = {'struct_type': struct_type, 'contract_mode': contract_mode,
                    'with_material': with_material}

    # 絕對價格 → 相對今日參考行情的偏差 %（優先於舊版相對指數）
    base_year = datetime.now().year
    prices = load_prices()
    material_deltas = {
        'rebar': {
            'input_price': rebar_price,
            'reference': reference_price('rebar', base_year, prices),
            'delta_pct': price_delta_pct('rebar', rebar_price, base_year, prices)
                         if rebar_price else rebar,
        },
        'concrete': {
            'input_price': concrete_price,
            'reference': reference_price('concrete', base_year, prices),
            'delta_pct': price_delta_pct('concrete', concrete_price, base_year, prices)
                         if concrete_price else concrete,
        },
        'labor': {'delta_pct': labor},
    }
    wf = {'rebar': material_deltas['rebar']['delta_pct'],
          'concrete': material_deltas['concrete']['delta_pct'],
          'labor': labor}
    whatif = wf if any(wf.values()) else None

    result = {
        'project_type': project_type,
        'area_ping': area_ping,
        'area_m2': round(area_ping * M2_PER_PING),
        'material_deltas': material_deltas,
    }

    # ── 三法三角驗證（新引擎）──
    result['cost_ensemble'] = ensemble_predict(
        cost_snaps, area_ping, target_conds, kind='cost',
        escalate=escalate, whatif=whatif)
    result['assumption_ensemble'] = ensemble_predict(
        assum_snaps, area_ping, target_conds, kind='assumption',
        escalate=escalate, whatif=whatif)

    def _build_pred(pts, target):
        """組裝單一回歸預估結果（cost / assumption 共用）"""
        if len(pts) >= 2:
            pred, r2, info = regression(pts, target)
            level, note = confidence_label(info['n'], r2, info.get('extrapolation', False))
            return {
                'predicted': pred, 'r2': r2, 'r2_adj': info.get('r2_adj'),
                'per_ping': pred / target if target else 0,
                'n': info['n'], 'slope': info.get('a'), 'intercept': info.get('b'),
                'se': info.get('se'), 't_crit': info.get('t_crit'),
                'pi_lower': info.get('pi_lower'), 'pi_upper': info.get('pi_upper'),
                'pi_band': info.get('pi_band', []),
                'extrapolation': info.get('extrapolation', False),
                'x_min': info.get('x_min'), 'x_max': info.get('x_max'),
                'residuals': info.get('residuals', []), 'outliers': info.get('outliers', []),
                'confidence': level, 'confidence_note': note,
                'unit_cost': unit_cost_stats(pts),
                'history_x': info.get('x', []), 'history_y': info.get('y', []),
            }
        if len(pts) == 1:
            pp = pts[0][1] / pts[0][0]
            return {
                'predicted': pp * target, 'r2': None, 'per_ping': pp, 'n': 1,
                'confidence': 'minimal', 'confidence_note': '僅 1 筆樣本，以單價直接換算',
                'unit_cost': unit_cost_stats(pts),
            }
        return None

    # Cost prediction（同步保留專案名/日期，與 history_x 索引對齊）
    cost_recs = [s for s in cost_snaps if s.get('area_ping', 0) >= 10]
    cost_pts = [(s['area_ping'], s['total_settle']) for s in cost_recs]
    cp = _build_pred(cost_pts, area_ping)
    if cp:
        cp['history_names'] = [s.get('display_name', '') for s in cost_recs]
        cp['history_dates'] = [s.get('read_date', '') for s in cost_recs]
        result['cost_prediction'] = cp
        if len(cost_pts) >= 2:
            result['cost_breakdown'] = render_breakdown_ratios(cost_snaps)

    # Assumption prediction
    assum_recs = [s for s in assum_snaps if s.get('area_ping', 0) >= 10]
    assum_pts = [(s['area_ping'], s['total_settle']) for s in assum_recs]
    ap = _build_pred(assum_pts, area_ping)
    if ap:
        ap['history_names'] = [s.get('display_name', '') for s in assum_recs]
        ap['history_dates'] = [s.get('read_date', '') for s in assum_recs]
        result['assumption_prediction'] = ap
        if len(assum_pts) >= 2:
            result['assumption_breakdown'] = render_assumption_ratios(assum_snaps)

    # Historical projects
    result['history_cost'] = [
        {'display_name': s.get('display_name'), 'area_ping': s.get('area_ping'),
         'total_settle': s.get('total_settle'), 'read_date': s.get('read_date'),
         'conditions': s.get('conditions', {})}
        for s in cost_snaps
    ]
    result['history_assumption'] = [
        {'display_name': s.get('display_name'), 'area_ping': s.get('area_ping'),
         'total_settle': s.get('total_settle'), 'read_date': s.get('read_date'),
         'conditions': s.get('conditions', {})}
        for s in assum_snaps
    ]

    return result


@app.get("/api/cost-index")
def get_cost_index():
    """營造物價指數表（年指數，內建近似值，可由 PUT 校正）"""
    return {'index': load_index(), 'struct_factors': STRUCT_FACTORS}


@app.put("/api/cost-index")
def update_cost_index(data: dict):
    """更新物價指數表，body: {"index": {"2024": 121.0, ...}}"""
    idx = data.get('index', {})
    if not isinstance(idx, dict) or not idx:
        raise HTTPException(400, "index 須為非空 dict")
    try:
        save_index(idx)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"指數格式錯誤: {e}")
    return {'status': 'ok', 'index': load_index()}


@app.get("/api/material-prices")
def get_material_prices():
    """大宗物料參考行情表（鋼筋 元/噸、混凝土 元/m³；內建近似值可校正）
    公開來源：豐興每週牌價 / 中鋼盤價 / 主計總處營造物價指數月報"""
    return {'prices': load_prices(),
            'units': {'rebar': '元/噸', 'concrete': '元/m³'},
            'names': {'rebar': '鋼筋', 'concrete': '預拌混凝土'}}


@app.put("/api/material-prices")
def update_material_prices(data: dict):
    """更新參考行情，body: {"prices": {"rebar": {"2026": 19000}, ...}}"""
    prices = data.get('prices', {})
    if not isinstance(prices, dict) or not prices:
        raise HTTPException(400, "prices 須為非空 dict")
    try:
        merged = load_prices()
        for mat, table in prices.items():
            if isinstance(table, dict):
                merged.setdefault(mat, {}).update(
                    {str(k): float(v) for k, v in table.items()})
        save_prices(merged)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"價格格式錯誤: {e}")
    return {'status': 'ok', 'prices': load_prices()}


@app.put("/api/snapshot/{table}/{sid}/conditions")
def update_snapshot_conditions(table: str, sid: int, data: dict):
    """更新快照條件（結構型式 / 發包方式 / 業主供料等），供預估相似度加權"""
    if table not in ('assumption_snapshots', 'cost_snapshots'):
        raise HTTPException(400, "Invalid table")
    conds = data.get('conditions', {})
    if not isinstance(conds, dict):
        raise HTTPException(400, "conditions 須為 dict")
    db_update_conditions(table, sid, conds)
    return {'status': 'ok', 'id': sid, 'conditions': conds}


# ═══════════════════════════════════════════════
# Batch Upload (auto-detect + batch save)
# ═══════════════════════════════════════════════
def _match_area(display_name, areas):
    """從 areas dict 匹配面積：先精確比對，再部分比對"""
    if display_name in areas:
        return areas[display_name]
    for key, val in areas.items():
        if display_name in key or key in display_name:
            return val
    return 0


@app.post("/api/batch-analyze")
async def batch_analyze(files: list[UploadFile] = File(...)):
    """批次上傳 — 每個檔案自動偵測假設工程 + 造價，回傳所有結果"""
    v14 = load_v14_module()
    areas = load_areas()
    results = []

    for uf in files:
        tmp = DATA_DIR / Path(uf.filename).name
        content = await uf.read()
        with open(tmp, 'wb') as f:
            f.write(content)

        try:
            raw = read_xlsx_via_xml(str(tmp))
            proj_name, cutoff = get_project_info(raw)
            dn = (clean_project_name(proj_name)
                  or extract_name_from_filename(str(tmp))
                  or extract_display_name(str(tmp)))
            file_date = (parse_date_str(cutoff)
                         or parse_date_str(os.path.basename(uf.filename))
                         or datetime.now().strftime('%Y-%m-%d'))
            detected_type = detect_project_type(dn)
            matched_area = _match_area(dn, areas)

            # ── Assumption parse ──
            try:
                cats = extract_categories(raw)
                ts = sum(cats[k]['settlement'] for k in ORDER)
                tb = sum(cats[k]['budget'] for k in ORDER)
                if ts > 0 or tb > 0:
                    items = {k: {'budget': cats[k]['budget'], 'settlement': cats[k]['settlement']}
                             for k in ORDER}
                    results.append({
                        'analysis_type': 'assumption',
                        'display_name': dn,
                        'project_full': proj_name,
                        'cutoff_date': cutoff or '',
                        'file_date': file_date,
                        'filename': uf.filename,
                        'total_budget': tb,
                        'total_settle': ts,
                        'items': items,
                        'detected_type': detected_type,
                        'area_ping': matched_area,
                    })
            except Exception:
                pass

            # ── Cost parse ──
            if v14:
                try:
                    proj = _build_proj_from_xml(raw)
                    clf = v14.classify_project(proj)
                    sb = proj['settlement']
                    total = sb['total'] if sb['total'] > 0 else clf['gi']
                    big8 = _aggregate_big8(clf['items'])

                    if total > 0:
                        items_list = []
                        for it in clf['items']:
                            if it['mode'] == 'sub_header':
                                continue
                            items_list.append({
                                'big': _BIG8_MAP.get(it['big'], it['big']),
                                'sub': it['sub'], 'name': it['name'],
                                'total': it['total'], 'qty': it.get('qty', 0),
                                'unit': it.get('unit', ''),
                            })

                        excel_filename = ''
                        try:
                            import openpyxl as oxl
                            wb = oxl.Workbook()
                            wb.remove(wb.active)
                            sf = v14.safe_filename(dn) or 'output'
                            # matched_area 為坪，轉 m² 供 Excel per-area 欄位
                            v14.write_cost_analysis(wb, proj, clf,
                                                    matched_area * M2_PER_PING,
                                                    f'{sf}_造價'[:31])
                            buf = io.BytesIO()
                            wb.save(buf)
                            buf.seek(0)
                            excel_filename = f"{sf}_{file_date.replace('-','')}.xlsx"
                            _cache_put((dn, file_date), buf.getvalue())
                        except Exception:
                            pass

                        results.append({
                            'analysis_type': 'cost',
                            'display_name': dn,
                            'file_date': file_date,
                            'filename': uf.filename,
                            'total_settle': total,
                            'big_groups': big8,
                            'items_list': items_list,
                            'unassigned_count': len(clf.get('unassigned', {})),
                            'detected_type': detected_type,
                            'excel_filename': excel_filename,
                            'area_ping': matched_area,
                        })
                except Exception:
                    pass

        except Exception as e:
            results.append({'filename': uf.filename, 'error': str(e)})

    return {'results': results, 'total_files': len(files)}


@app.post("/api/batch-save")
def batch_save(data: BatchSaveIn):
    """批次儲存解析結果到 DB"""
    saved = []
    errors = []
    areas = load_areas()
    areas_changed = False

    for item in data.items:
        try:
            dn = item['display_name']
            rd = item.get('file_date') or datetime.now().strftime('%Y-%m-%d')
            area_ping = float(item.get('area_ping', 0))
            project_type = item.get('project_type', '其他')

            atype = item.get('analysis_type', '')
            if atype == 'assumption':
                if db_check_duplicate('assumption_snapshots', dn, rd):
                    errors.append({'display_name': dn, 'error': f'{dn} 日期 {rd} 已存在'})
                    continue
                db_insert_assumption(
                    dn, item.get('project_full', ''), item.get('cutoff_date', ''),
                    area_ping, item.get('total_budget', 0), item.get('total_settle', 0),
                    item.get('items', {}), item.get('filename', ''),
                    file_date=rd, project_type=project_type, conditions={},
                )
            elif atype == 'cost':
                if db_check_duplicate('cost_snapshots', dn, rd):
                    errors.append({'display_name': dn, 'error': f'{dn} 日期 {rd} 已存在'})
                    continue
                am = area_ping / 0.3025 if area_ping > 0 else 0
                xb = _cache_pop((dn, rd))
                db_insert_cost(
                    dn, '', area_ping, am,
                    item.get('total_settle', 0), item.get('big_groups', {}),
                    item.get('items_list', []),
                    item.get('unassigned_count', 0), item.get('filename', ''),
                    xb, item.get('excel_filename', ''),
                    file_date=rd, project_type=project_type, conditions={},
                )
            else:
                errors.append({'display_name': dn, 'error': f'未知 analysis_type: {atype}'})
                continue

            # Update area
            if area_ping > 0:
                areas[dn] = area_ping
                areas_changed = True

            saved.append({'display_name': dn, 'analysis_type': item['analysis_type']})
        except Exception as e:
            errors.append({'display_name': item.get('display_name', '?'), 'error': str(e)})

    if areas_changed:
        save_areas(areas)

    return {'saved': saved, 'errors': errors,
            'total_saved': len(saved), 'total_errors': len(errors)}


# ═══════════════════════════════════════════════
# History
# ═══════════════════════════════════════════════
@app.get("/api/history")
def get_history(table: str = Query('assumption_snapshots')):
    """歷史快照清單（僅摘要，不含 items 明細以提升效能）"""
    if table == 'assumption_snapshots':
        names = db_get_all_assumption_names()
        snaps_by_dn = {}
        for dn in names:
            snaps = db_get_assumption_snaps(dn)
            # Strip heavy fields for history list
            for s in snaps:
                s.pop('items', None)
                s.pop('items_json', None)
                s.pop('conditions_json', None)
            snaps_by_dn[dn] = snaps
        return {'names': names, 'snapshots': snaps_by_dn}
    elif table == 'cost_snapshots':
        names = db_get_all_cost_names()
        snaps_by_dn = {}
        for dn in names:
            snaps = db_get_cost_snaps(dn)
            for s in snaps:
                s['big_groups'] = _normalize_big_groups(s.get('big_groups', {}))
                # Strip heavy fields for history list
                s.pop('items', None)
                s.pop('items_json', None)
                s.pop('conditions_json', None)
            snaps_by_dn[dn] = snaps
        return {'names': names, 'snapshots': snaps_by_dn}
    raise HTTPException(400, "Invalid table")


@app.delete("/api/snapshot/{table}/{sid}")
def delete_snapshot(table: str, sid: int):
    if table not in ('assumption_snapshots', 'cost_snapshots'):
        raise HTTPException(400, "Invalid table")
    db_delete_snapshot(table, sid)
    return {'status': 'ok'}


# ═══════════════════════════════════════════════
# Areas
# ═══════════════════════════════════════════════
@app.get("/api/areas")
def get_areas():
    return load_areas()


@app.put("/api/areas")
def update_areas(data: AreasIn):
    save_areas(data.areas)
    return {'status': 'ok'}


# ═══════════════════════════════════════════════
# Type counts (for prediction page)
# ═══════════════════════════════════════════════
@app.get("/api/type-counts")
def get_type_counts():
    a, c = db_get_type_counts()
    return {'assumption': a, 'cost': c}


# ═══════════════════════════════════════════════
# DB Health & Backup
# ═══════════════════════════════════════════════
BACKUP_DIR = Path("./backups")

@app.get("/api/health")
def db_health():
    """資料品質健康檢查"""
    import sqlite3
    db = sqlite3.connect(str(DB_FILE))
    try:
        db.row_factory = sqlite3.Row

        # Assumption stats
        a_total = db.execute("SELECT COUNT(*) FROM assumption_snapshots").fetchone()[0]
        a_zero_settle = db.execute("SELECT COUNT(*) FROM assumption_snapshots WHERE total_settle = 0 OR total_settle IS NULL").fetchone()[0]
        a_no_area = db.execute("SELECT COUNT(*) FROM assumption_snapshots WHERE area_ping = 0 OR area_ping IS NULL").fetchone()[0]

        # Cost stats
        c_total = db.execute("SELECT COUNT(*) FROM cost_snapshots").fetchone()[0]
        c_zero_settle = db.execute("SELECT COUNT(*) FROM cost_snapshots WHERE total_settle = 0 OR total_settle IS NULL").fetchone()[0]
        c_no_area = db.execute("SELECT COUNT(*) FROM cost_snapshots WHERE area_ping = 0 OR area_ping IS NULL").fetchone()[0]

        # Problem snapshots details
        problems = []
        rows = db.execute(
            "SELECT id, display_name, read_date, 'cost' as source FROM cost_snapshots WHERE total_settle = 0 OR total_settle IS NULL"
        ).fetchall()
        for r in rows:
            problems.append({'id': r['id'], 'name': r['display_name'], 'date': r['read_date'],
                             'source': 'cost', 'issue': 'settle=0'})
        rows2 = db.execute(
            "SELECT id, display_name, read_date, 'assumption' as source FROM assumption_snapshots WHERE area_ping = 0 OR area_ping IS NULL"
        ).fetchall()
        for r in rows2:
            problems.append({'id': r['id'], 'name': r['display_name'], 'date': r['read_date'],
                             'source': 'assumption', 'issue': 'area=0'})

        # DB file info
        db_size = os.path.getsize(str(DB_FILE)) if DB_FILE.exists() else 0

        # Backup info
        backups = []
        if BACKUP_DIR.exists():
            for f in sorted(BACKUP_DIR.glob("kg_history_*.db"), reverse=True):
                backups.append({'filename': f.name, 'size': f.stat().st_size,
                                'date': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')})
    finally:
        db.close()

    return {
        'assumption': {'total': a_total, 'zero_settle': a_zero_settle, 'no_area': a_no_area},
        'cost': {'total': c_total, 'zero_settle': c_zero_settle, 'no_area': c_no_area},
        'problems': problems,
        'db_size': db_size,
        'backups': backups[:10],  # last 10
        'score': _health_score(a_total, a_zero_settle, a_no_area, c_total, c_zero_settle, c_no_area),
    }


def _health_score(a_total, a_zs, a_na, c_total, c_zs, c_na):
    """0~100 health score — count each snapshot at most once as 'has issue'"""
    total = a_total + c_total
    if total == 0:
        return 100
    # Use max per table to avoid double-counting a snapshot with multiple issues
    a_issues = max(a_zs, a_na)
    c_issues = max(c_zs, c_na)
    issues = a_issues + c_issues
    return max(0, round(100 * (1 - issues / total)))


@app.post("/api/backup")
def create_backup():
    """建立 DB 備份"""
    if not DB_FILE.exists():
        raise HTTPException(404, "資料庫不存在")
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = BACKUP_DIR / f"kg_history_{ts}.db"
    shutil.copy2(str(DB_FILE), str(dest))
    # Also backup areas
    area_file = Path("./kg_areas.json")
    if area_file.exists():
        shutil.copy2(str(area_file), BACKUP_DIR / f"kg_areas_{ts}.json")
    return {
        'status': 'ok',
        'filename': dest.name,
        'size': dest.stat().st_size,
        'timestamp': ts,
    }


@app.get("/api/backup/download/{filename}")
def download_backup(filename: str):
    """下載備份檔"""
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(400, "無效檔名")
    path = (BACKUP_DIR / filename).resolve()
    if not str(path).startswith(str(BACKUP_DIR.resolve())):
        raise HTTPException(400, "無效路徑")
    if not path.exists():
        raise HTTPException(404, "備份檔不存在")
    return FileResponse(str(path), filename=filename,
                        media_type="application/octet-stream")


# ═══════════════════════════════════════════════
# Static frontend (CDN mode — no build step)
# ═══════════════════════════════════════════════
FRONTEND_DIR = Path(__file__).parent / "frontend"

if FRONTEND_DIR.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    # Mount after explicit routes — Starlette checks routes before mounts,
    # so /api/* and /docs still take priority.
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend-static")
    # Also serve root-level assets (js/, styles.css) via a catch-all mount
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
