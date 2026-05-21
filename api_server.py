#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 後端 — 成本管理監測系統 REST API
啟動：uvicorn api_server:app --reload --port 8000
"""
import os, io, json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from core import (
    DATA_DIR, ORDER, PROJECT_TYPES, M2_PER_PING, PING_PER_M2,
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
    db_get_cost_excel, db_delete_snapshot, db_clear_all, db_check_duplicate,
    db_get_by_type, db_get_type_counts,
    # areas
    load_areas, save_areas, sync_area,
    # analysis
    regression, render_breakdown_ratios, render_assumption_ratios,
)
from core.utils import load_v14_module

# ── Init ──
DATA_DIR.mkdir(exist_ok=True)
init_db()

app = FastAPI(title="KG 成本管理 API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# ═══════════════════════════════════════════════
# Parse KG
# ═══════════════════════════════════════════════
@app.post("/api/parse-kg")
async def parse_kg(files: list[UploadFile] = File(...)):
    """上傳 .xlsx，回傳解析後的假設工程 JSON"""
    results = []
    for uf in files:
        tmp = DATA_DIR / uf.filename
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


# ═══════════════════════════════════════════════
# Cost
# ═══════════════════════════════════════════════
@app.get("/api/cost/{dn}")
def get_cost(dn: str):
    snaps = db_get_cost_snaps(dn)
    return {'display_name': dn, 'count': len(snaps), 'snapshots': snaps}


@app.post("/api/cost/analyze")
async def cost_analyze(files: list[UploadFile] = File(...)):
    """上傳檔案，執行造價分析，回傳結果（含 Excel download URL）"""
    v14 = load_v14_module()
    if not v14:
        raise HTTPException(500, "找不到 kg_cost_analysis_v14.py")

    results = []
    for uf in files:
        tmp = DATA_DIR / uf.filename
        content = await uf.read()
        with open(tmp, 'wb') as f:
            f.write(content)
        try:
            proj = v14.read_kg_file(str(tmp))
            raw_pn = proj.get('project_name', '') or ''
            dn = (clean_project_name(raw_pn)
                  or extract_name_from_filename(str(tmp))
                  or extract_display_name(str(tmp)))
            try:
                raw = read_xlsx_via_xml(str(tmp))
                _, cutoff = get_project_info(raw)
            except:
                cutoff = ''
            file_date = (parse_date_str(cutoff)
                         or parse_date_str(os.path.basename(uf.filename))
                         or datetime.now().strftime('%Y-%m-%d'))
            clf = v14.classify_project(proj)
            sb = proj['settlement']
            total = sb['total'] if sb['total'] > 0 else clf['gi']

            big_sum = {}
            items_list = []
            for it in clf['items']:
                if it['mode'] == 'sub_header': continue
                big_sum[it['big']] = big_sum.get(it['big'], 0) + it['total']
                items_list.append({
                    'big': it['big'], 'sub': it['sub'], 'name': it['name'],
                    'total': it['total'], 'qty': it.get('qty', 0), 'unit': it.get('unit', ''),
                })
            results.append({
                'display_name': dn,
                'file_date': file_date,
                'filename': uf.filename,
                'total_settle': total,
                'big_groups': big_sum,
                'items': items_list,
                'unassigned_count': len(clf.get('unassigned', {})),
                'detected_type': detect_project_type(dn),
            })
        except Exception as e:
            results.append({'filename': uf.filename, 'error': str(e)})
    return {'results': results}


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
):
    """回歸預估造價"""
    cost_snaps = db_get_by_type('cost_snapshots', project_type)
    assum_snaps = db_get_by_type('assumption_snapshots', project_type)

    result = {
        'project_type': project_type,
        'area_ping': area_ping,
        'area_m2': round(area_ping * M2_PER_PING),
    }

    # Cost prediction
    cost_pts = [(s['area_ping'], s['total_settle'])
                for s in cost_snaps if s.get('area_ping', 0) >= 10]
    if len(cost_pts) >= 2:
        pred, r2, info = regression(cost_pts, area_ping)
        result['cost_prediction'] = {
            'predicted': pred, 'r2': r2, 'per_ping': pred / area_ping if area_ping else 0,
            'n': info['n'], 'slope': info.get('a'), 'intercept': info.get('b'), 'se': info.get('se'),
            'history_x': info.get('x', []), 'history_y': info.get('y', []),
        }
        result['cost_breakdown'] = render_breakdown_ratios(cost_snaps)
    elif len(cost_pts) == 1:
        pp = cost_pts[0][1] / cost_pts[0][0]
        result['cost_prediction'] = {
            'predicted': pp * area_ping, 'r2': None, 'per_ping': pp, 'n': 1,
        }

    # Assumption prediction
    assum_pts = [(s['area_ping'], s['total_settle'])
                 for s in assum_snaps if s.get('area_ping', 0) >= 10]
    if len(assum_pts) >= 2:
        pred_a, r2_a, info_a = regression(assum_pts, area_ping)
        result['assumption_prediction'] = {
            'predicted': pred_a, 'r2': r2_a, 'per_ping': pred_a / area_ping if area_ping else 0,
            'n': info_a['n'], 'slope': info_a.get('a'), 'intercept': info_a.get('b'), 'se': info_a.get('se'),
            'history_x': info_a.get('x', []), 'history_y': info_a.get('y', []),
        }
        result['assumption_breakdown'] = render_assumption_ratios(assum_snaps)
    elif len(assum_pts) == 1:
        pp = assum_pts[0][1] / assum_pts[0][0]
        result['assumption_prediction'] = {
            'predicted': pp * area_ping, 'r2': None, 'per_ping': pp, 'n': 1,
        }

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


# ═══════════════════════════════════════════════
# History
# ═══════════════════════════════════════════════
@app.get("/api/history")
def get_history(table: str = Query('assumption_snapshots')):
    if table == 'assumption_snapshots':
        names = db_get_all_assumption_names()
        return {'names': names, 'snapshots': {dn: db_get_assumption_snaps(dn) for dn in names}}
    elif table == 'cost_snapshots':
        names = db_get_all_cost_names()
        return {'names': names, 'snapshots': {dn: db_get_cost_snaps(dn) for dn in names}}
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


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
