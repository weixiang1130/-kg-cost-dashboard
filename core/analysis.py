# -*- coding: utf-8 -*-
"""回歸分析與預估計算"""
import json
import numpy as np
from .constants import ORDER


def regression(points: list, target_x: float):
    """線性回歸預估
    points: [(x, y), ...]
    回傳: (prediction, r2, info_dict)
    """
    if len(points) < 2:
        return None, None, {'n': len(points)}
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    a, b = np.polyfit(x, y, 1)
    y_pred = a * x + b
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    pred = a * target_x + b
    se = np.sqrt(ss_res / (len(points) - 2)) if len(points) > 2 else 0
    return max(pred, 0), r2, {
        'n': len(points), 'a': a, 'b': b, 'se': se,
        'x': x.tolist(), 'y': y.tolist(),
    }


def render_breakdown_ratios(cost_snaps: list) -> dict:
    """計算八大類平均佔比，回傳 {大類: 佔比}"""
    valid = [s for s in cost_snaps if s.get('area_ping', 0) >= 10 and s.get('total_settle', 0) > 0]
    if not valid:
        return {}
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
            if t > 0 and b in bg:
                pcts.append(bg[b] / t)
        avg_pcts[b] = sum(pcts) / len(pcts) if pcts else 0
    return avg_pcts


def render_assumption_ratios(assum_snaps: list) -> dict:
    """計算 13 項假設工程平均佔比，回傳 {項目: 佔比}"""
    valid = [s for s in assum_snaps if s.get('area_ping', 0) >= 10]
    if not valid:
        return {}
    avg_items = {}
    for n in ORDER:
        vals = []
        for s in valid:
            items = s.get('items', {})
            if isinstance(items, str): items = json.loads(items)
            t = s.get('total_settle', 0)
            v = items.get(n, {})
            settle = v.get('settlement', 0) if isinstance(v, dict) else 0
            if t > 0:
                vals.append(settle / t)
        avg_items[n] = sum(vals) / len(vals) if vals else 0
    return avg_items
