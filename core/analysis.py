# -*- coding: utf-8 -*-
"""回歸分析與預估計算"""
import json
import numpy as np
from .constants import ORDER

# t 分佈 97.5 百分位（95% 雙尾），key = 自由度；scipy 不可用時的 fallback
_T_TABLE = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
            6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
            15: 2.131, 20: 2.086, 30: 2.042}


def _t_crit(dof: int) -> float:
    """95% 雙尾 t 臨界值"""
    try:
        from scipy import stats as _st
        return float(_st.t.ppf(0.975, dof))
    except Exception:
        if dof in _T_TABLE:
            return _T_TABLE[dof]
        for k in sorted(_T_TABLE, reverse=True):
            if dof >= k:
                return _T_TABLE[k]
        return 1.96


def regression(points: list, target_x: float):
    """線性回歸預估（含 t 分佈 95% 預測區間）
    points: [(x, y), ...]
    回傳: (prediction, r2, info_dict)

    info_dict:
      n, a, b, se, x, y           — 與舊版相容
      r2_adj                      — 調整後 R²（n>2 才有，n=2 時 R² 恆為 1 無意義）
      t_crit                      — t 臨界值（df = n-2）
      pi_lower / pi_upper         — target_x 的 95% 預測區間（含新觀測誤差，
                                    寬度隨 (x0-x̄)²/Sxx 增加 → 喇叭形）
      pi_band                     — [[x, lower, upper], ...] 21 點，供前端畫區間帶
      extrapolation               — target_x 是否超出歷史資料範圍
      x_min / x_max               — 歷史 x 範圍
      residuals                   — 各點殘差
      outliers                    — 標準化殘差絕對值 > 2 的點 index
    """
    if len(points) < 2:
        return None, None, {'n': len(points)}
    x = np.array([p[0] for p in points], dtype=float)
    y = np.array([p[1] for p in points], dtype=float)
    n = len(points)
    a, b = np.polyfit(x, y, 1)
    y_fit = a * x + b
    resid = y - y_fit
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    r2_adj = 1 - (1 - r2) * (n - 1) / (n - 2) if n > 2 else None

    pred = a * target_x + b
    dof = n - 2

    pi_lower = pi_upper = max(pred, 0)
    pi_band = []
    se = 0.0
    t_crit = None
    if dof > 0:
        se = float(np.sqrt(ss_res / dof))  # residual standard error
        t_crit = _t_crit(dof)
        x_mean = float(np.mean(x))
        sxx = float(np.sum((x - x_mean) ** 2)) or 1.0

        def _pi_half(x0):
            # 預測區間半寬：含新觀測誤差項 (1)、均值估計誤差 (1/n)、槓桿項
            return t_crit * se * float(np.sqrt(1 + 1 / n + (x0 - x_mean) ** 2 / sxx))

        half = _pi_half(target_x)
        pi_lower = max(pred - half, 0)
        pi_upper = pred + half

        x_lo = min(float(x.min()), target_x) * 0.95
        x_hi = max(float(x.max()), target_x) * 1.05
        for i in range(21):
            xi = x_lo + (x_hi - x_lo) * i / 20
            yi = a * xi + b
            h = _pi_half(xi)
            pi_band.append([xi, max(yi - h, 0), yi + h])

    outliers = []
    if dof > 0 and se > 0:
        std_resid = resid / se
        outliers = [i for i, sr in enumerate(std_resid) if abs(sr) > 2]

    extrapolation = bool(target_x < float(x.min()) or target_x > float(x.max()))

    return max(pred, 0), r2, {
        'n': n, 'a': a, 'b': b, 'se': se,
        'r2_adj': r2_adj, 't_crit': t_crit,
        'pi_lower': pi_lower, 'pi_upper': pi_upper, 'pi_band': pi_band,
        'extrapolation': extrapolation,
        'x_min': float(x.min()), 'x_max': float(x.max()),
        'residuals': resid.tolist(), 'outliers': outliers,
        'x': x.tolist(), 'y': y.tolist(),
    }


def confidence_label(n: int, r2, extrapolation: bool = False):
    """綜合樣本數、R²、外插與否的信心等級
    回傳 (level, note)；level ∈ {'high','mid','low','minimal'}
    """
    if n < 3 or r2 is None:
        return 'minimal', f'樣本僅 {n} 筆，迴歸線恆過所有點，R² 無鑑別力，僅供參考'
    if r2 >= 0.9:
        level = 'high'
    elif r2 >= 0.7:
        level = 'mid'
    else:
        level = 'low'
    notes = []
    if extrapolation:
        # 外插：預測點超出歷史範圍，可靠度降一級
        level = {'high': 'mid', 'mid': 'low', 'low': 'minimal'}[level]
        notes.append('預測面積超出歷史樣本範圍（外插），可靠度降級')
    if n < 5:
        notes.append(f'樣本數 {n} 筆偏少，建議補充同類案例')
    return level, '；'.join(notes)


def unit_cost_stats(points: list) -> dict:
    """歷史單價（y/x）統計：min / median / max / mean"""
    pers = sorted(y / x for x, y in points if x > 0)
    if not pers:
        return {}
    n = len(pers)
    median = pers[n // 2] if n % 2 else (pers[n // 2 - 1] + pers[n // 2]) / 2
    return {'min': pers[0], 'median': median, 'max': pers[-1],
            'mean': sum(pers) / n, 'n': n}


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
