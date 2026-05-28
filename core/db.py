# -*- coding: utf-8 -*-
"""SQLite 資料庫操作"""
import json
import sqlite3
from datetime import datetime
from .constants import DB_FILE


_VALID_TABLES = frozenset({'assumption_snapshots', 'cost_snapshots'})


def _check_table(table):
    if table not in _VALID_TABLES:
        raise ValueError(f"Invalid table name: {table}")


def _db():
    return sqlite3.connect(str(DB_FILE))


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


# ── Assumption ──

def db_insert_assumption(dn, pf, cd, ap, tb, ts, items, sf,
                         file_date=None, project_type='其他', conditions=None):
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
    c.close()
    return [r[0] for r in rows]


# ── Cost ──

def db_insert_cost(dn, pf, ap, am, ts, bg, items, un, sf, xb, xf,
                   file_date=None, project_type='其他', conditions=None):
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
    cols = ("id, display_name, project_full, read_date, area_ping, area_m2, "
            "total_settle, big_groups_json, items_json, unassigned_count, "
            "source_filename, excel_filename, project_type, conditions_json")
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
    c.close()
    return [r[0] for r in rows]


def db_get_cost_excel(sid):
    c = _db()
    row = c.execute("SELECT excel_blob, excel_filename FROM cost_snapshots WHERE id=?", (sid,)).fetchone()
    c.close()
    return (row[0], row[1]) if row else (None, None)


# ── Common ──

def db_update_cost_area(sid, area_ping):
    area_m2 = area_ping / 0.3025 if area_ping > 0 else 0
    with _db() as c:
        c.execute("UPDATE cost_snapshots SET area_ping=?, area_m2=? WHERE id=?",
                  (area_ping, area_m2, sid))


def db_update_assumption_area(sid, area_ping):
    with _db() as c:
        c.execute("UPDATE assumption_snapshots SET area_ping=? WHERE id=?",
                  (area_ping, sid))


def db_delete_snapshot(table, sid):
    _check_table(table)
    with _db() as c:
        c.execute(f"DELETE FROM {table} WHERE id=?", (sid,))


def db_clear_all(table):
    _check_table(table)
    with _db() as c:
        c.execute(f"DELETE FROM {table}")


def db_check_duplicate(table, dn, read_date):
    _check_table(table)
    c = _db()
    n = c.execute(f"SELECT COUNT(*) FROM {table} WHERE display_name=? AND read_date=?",
                  (dn, read_date)).fetchone()[0]
    c.close()
    return n > 0


def db_get_by_type(table, pt):
    _check_table(table)
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


def db_get_type_counts():
    c = _db()
    rows_a = c.execute("SELECT project_type, COUNT(*) as cnt FROM assumption_snapshots GROUP BY project_type").fetchall()
    rows_c = c.execute("SELECT project_type, COUNT(*) as cnt FROM cost_snapshots GROUP BY project_type").fetchall()
    c.close()
    a = {r[0]: r[1] for r in rows_a}
    cc = {r[0]: r[1] for r in rows_c}
    return a, cc
