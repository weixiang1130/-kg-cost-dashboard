#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 快速驗證腳本
用法：先啟動 API server，再執行此腳本
  start_api.bat          (另一個視窗)
  python test_api.py
"""
import requests
import sys

BASE = "http://127.0.0.1:8000"
passed = failed = 0

def test(name, method, path, expected_status=200, **kwargs):
    global passed, failed
    url = f"{BASE}{path}"
    try:
        r = getattr(requests, method)(url, **kwargs)
        ok = r.status_code == expected_status
        status = "PASS" if ok else "FAIL"
        if ok: passed += 1
        else: failed += 1
        print(f"  [{status}] {method.upper()} {path} → {r.status_code}"
              + ("" if ok else f" (expected {expected_status})"))
        if ok and method == 'get':
            data = r.json()
            # 簡要印出資料量
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, list):
                        print(f"         {k}: {len(v)} items")
                    elif isinstance(v, (int, float, str)):
                        print(f"         {k}: {v}")
        return r
    except requests.ConnectionError:
        failed += 1
        print(f"  [FAIL] {method.upper()} {path} → 連線失敗（API server 是否啟動？）")
        return None

print("=" * 50)
print("  KG 成本管理 API — 端點驗證")
print("=" * 50)

# 1. Projects overview
print("\n[1] 專案總覽")
test("projects", "get", "/api/projects")

# 2. Type counts
print("\n[2] 類型統計")
test("type-counts", "get", "/api/type-counts")

# 3. Areas
print("\n[3] 面積設定")
test("areas", "get", "/api/areas")

# 4. History - assumption
print("\n[4] 歷史記錄 — 假設工程")
test("history-a", "get", "/api/history?table=assumption_snapshots")

# 5. History - cost
print("\n[5] 歷史記錄 — 造價分析")
test("history-c", "get", "/api/history?table=cost_snapshots")

# 6. Prediction (needs valid type + area)
print("\n[6] 投標預估")
test("prediction", "get", "/api/prediction?project_type=FAB&area_ping=20000")

# 7. Get assumption by name (use first available)
print("\n[7] 假設工程查詢")
r = requests.get(f"{BASE}/api/projects")
if r.ok:
    projects = r.json().get('projects', [])
    if projects:
        dn = projects[0]['display_name']
        test("assumption", "get", f"/api/assumption/{dn}")
    else:
        print("  [SKIP] 無專案資料")

# 8. Get cost by name
print("\n[8] 造價分析查詢")
if r.ok and projects:
    dn = projects[0]['display_name']
    test("cost", "get", f"/api/cost/{dn}")

# 9. Invalid table (should 400)
print("\n[9] 錯誤處理測試")
test("bad-table", "get", "/api/history?table=bad_table", expected_status=400)

# Summary
print("\n" + "=" * 50)
print(f"  結果：{passed} passed, {failed} failed")
print("=" * 50)
sys.exit(0 if failed == 0 else 1)
