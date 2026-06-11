# -*- coding: utf-8 -*-
"""投標預估引擎 — 三法三角驗證（業界實務）

A. 時間調整單價法：歷史單價 × 物價指數調整 → 相似度加權中位數（主力錨點）
B. 回歸法：對「調整後」金額做線性回歸（負斜率自動降權示警）
C. 分項組合法：八大類/13 項各自加權單價 → 結構型式係數調整 → 加總

綜合建議值 = 三法依可靠度加權；區間取各法包絡的加權平均。
所有經驗係數（結構型式、相似度衰減、What-if 傳導）皆集中於本檔頂部，可由成控團隊校正。
"""
import json
import math
from datetime import date
from .analysis import regression
from .cost_index import load_index, escalation_factor

# ── 經驗係數（可校正）──────────────────────────────
# 結構型式相對單價係數（針對結構工程大類；RC 為基準）
STRUCT_FACTORS = {'RC': 1.00, 'SC': 1.15, 'SRC': 1.30}

# 相似度權重參數
SIM_TIME_DECAY = 0.85      # 每隔一年 ×0.85（物價已另調，此處反映規格/工法演進）
SIM_AREA_SIGMA = 0.6       # 面積相似度：log 距離高斯衰減
SIM_STRUCT_DIFF = 0.6      # 結構型式不同
SIM_STRUCT_UNKNOWN = 0.85  # 結構型式未知
SIM_CONTRACT_DIFF = 0.8    # 發包方式不同
SIM_SUPPLY_DIFF = 0.5      # 業主供料條件不同（單價失真風險高）
SIM_UNKNOWN = 0.9          # 其他條件未知的中性權重

# What-if 行情傳導（與前端一致）
WHATIF_REBAR_IN_STRUCT = 0.45     # 鋼筋約佔結構工程
WHATIF_CONCRETE_IN_STRUCT = 0.35  # 混凝土約佔結構工程
WHATIF_LABOR_OF_TOTAL = 0.30      # 工資約佔總造價
DEFAULT_STRUCT_SHARE = 0.40       # 無分解資料時結構工程佔比預設

STRUCT_CAT = '結構工程'

# 三法混合基礎權重
BLEND_W_UNIT = 1.0
BLEND_W_REG = 1.0
BLEND_W_COMP = 0.8
NEG_SLOPE_PENALTY = 0.2   # 回歸負斜率（面積越大造價越低，不合理）時的權重折減


# ── 工具 ──────────────────────────────────────────
def _conds(snap) -> dict:
    c = snap.get('conditions', {})
    if isinstance(c, str):
        try: c = json.loads(c)
        except Exception: c = {}
    return c if isinstance(c, dict) else {}


def _year(s):
    try: return int(str(s)[:4])
    except (ValueError, TypeError): return None


def weighted_quantile(values, weights, q):
    """加權分位數（q ∈ [0,1]）"""
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    if total <= 0:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= q * total:
            return v
    return pairs[-1][0]


def similarity_weight(snap, target_area, target_conds, base_year) -> dict:
    """單一歷史案例對目標條件的相似度權重（各因子相乘）
    回傳 {'weight', 'factors': {...}} 供前端透明呈現
    """
    factors = {}
    # 時間：越久遠規格/工法差異越大（物價已另行調整）
    sy = _year(snap.get('read_date', ''))
    years_ago = max(0, (base_year or 0) - sy) if sy and base_year else 0
    factors['time'] = SIM_TIME_DECAY ** min(years_ago, 10)
    # 面積規模：log 距離高斯
    a = snap.get('area_ping', 0)
    if a > 0 and target_area > 0:
        d = math.log(a / target_area)
        factors['area'] = math.exp(-(d * d) / (2 * SIM_AREA_SIGMA ** 2))
    else:
        factors['area'] = SIM_UNKNOWN
    # 結構型式
    sc = _conds(snap)
    s_struct = (sc.get('struct_type') or '').upper()
    t_struct = (target_conds.get('struct_type') or '').upper()
    if not s_struct or not t_struct:
        factors['struct'] = SIM_STRUCT_UNKNOWN if t_struct else 1.0
    else:
        factors['struct'] = 1.0 if s_struct == t_struct else SIM_STRUCT_DIFF
    # 發包方式
    s_cm = sc.get('contract_mode') or ''
    t_cm = target_conds.get('contract_mode') or ''
    if not s_cm or not t_cm:
        factors['contract'] = SIM_UNKNOWN if t_cm else 1.0
    else:
        factors['contract'] = 1.0 if s_cm == t_cm else SIM_CONTRACT_DIFF
    # 業主供料
    s_sup = sc.get('with_material') or ''
    t_sup = target_conds.get('with_material') or ''
    if not s_sup or not t_sup:
        factors['supply'] = SIM_UNKNOWN if t_sup else 1.0
    else:
        factors['supply'] = 1.0 if s_sup == t_sup else SIM_SUPPLY_DIFF

    w = 1.0
    for v in factors.values():
        w *= v
    return {'weight': w, 'factors': factors}


def _whatif_overall_factor(whatif, struct_share):
    """What-if 對總價的傳導係數（單價法/回歸法用）"""
    if not whatif:
        return 1.0
    return 1.0 + struct_share * (
        WHATIF_REBAR_IN_STRUCT * whatif.get('rebar', 0) / 100 +
        WHATIF_CONCRETE_IN_STRUCT * whatif.get('concrete', 0) / 100
    ) + WHATIF_LABOR_OF_TOTAL * whatif.get('labor', 0) / 100


# ── 主引擎 ────────────────────────────────────────
def ensemble_predict(snaps, target_area, target_conds=None, kind='cost',
                     base_date=None, escalate=True, whatif=None):
    """三法三角驗證預估
    snaps: 同類型歷史快照（含 area_ping / total_settle / read_date /
           conditions / big_groups 或 items）
    回傳 dict（methods / blended / cases / escalation / confidence）
    """
    target_conds = target_conds or {}
    base_date = base_date or date.today().isoformat()
    base_year = _year(base_date)
    idx = load_index()

    valid = [s for s in snaps
             if s.get('area_ping', 0) >= 10 and s.get('total_settle', 0) > 0]
    if not valid:
        return None

    # ── 案例前處理：物價調整 + 相似度 ──
    cases = []
    for s in valid:
        esc = escalation_factor(s.get('read_date', ''), base_date, idx) if escalate else 1.0
        sim = similarity_weight(s, target_area, target_conds, base_year)
        sc = _conds(s)
        cases.append({
            'display_name': s.get('display_name', ''),
            'read_date': s.get('read_date', ''),
            'area': s['area_ping'],
            'settle': s['total_settle'],
            'esc_factor': esc,
            'esc_settle': s['total_settle'] * esc,
            'esc_pp': s['total_settle'] * esc / s['area_ping'],
            'weight': sim['weight'],
            'sim_factors': sim['factors'],
            'struct_type': sc.get('struct_type', ''),
            'contract_mode': sc.get('contract_mode', ''),
            'with_material': sc.get('with_material', ''),
            'snap': s,
        })

    pps = [c['esc_pp'] for c in cases]
    ws = [c['weight'] for c in cases]
    n = len(cases)

    # ── 結構工程佔比（What-if 傳導、分項法都要用）──
    struct_share = DEFAULT_STRUCT_SHARE
    cat_field = 'big_groups' if kind == 'cost' else 'items'
    shares = []
    for c in cases:
        bg = c['snap'].get(cat_field, {})
        if isinstance(bg, str):
            try: bg = json.loads(bg)
            except Exception: bg = {}
        if kind == 'cost' and isinstance(bg, dict) and bg.get(STRUCT_CAT, 0) > 0:
            shares.append((bg[STRUCT_CAT] / c['settle'], c['weight']))
    if shares:
        struct_share = sum(v * w for v, w in shares) / (sum(w for _, w in shares) or 1)

    wf_overall = _whatif_overall_factor(whatif, struct_share)

    # ── 方法 A：時間調整單價法（加權分位數）──
    p50 = weighted_quantile(pps, ws, 0.5)
    p20 = weighted_quantile(pps, ws, 0.2)
    p80 = weighted_quantile(pps, ws, 0.8)
    n_eff = (sum(ws) ** 2 / sum(w * w for w in ws)) if any(ws) else 0  # Kish 有效樣本數
    m_unit = {
        'predicted': p50 * target_area * wf_overall,
        'low': p20 * target_area * wf_overall,
        'high': p80 * target_area * wf_overall,
        'per_ping': p50 * wf_overall,
        'n': n, 'n_eff': round(n_eff, 1),
    }

    # ── 方法 B：回歸法（對調整後金額回歸）──
    m_reg = None
    reg_warning = ''
    if n >= 2:
        pts = [(c['area'], c['esc_settle']) for c in cases]
        pred, r2, info = regression(pts, target_area)
        if info.get('a') is not None and info['a'] < 0:
            reg_warning = '回歸斜率為負（面積越大造價越低），樣本可能含異常資料，已降低此法權重'
        m_reg = {
            'predicted': pred * wf_overall,
            'low': (info.get('pi_lower') or pred) * wf_overall,
            'high': (info.get('pi_upper') or pred) * wf_overall,
            'r2': r2, 'r2_adj': info.get('r2_adj'),
            'slope': info.get('a'), 'intercept': info.get('b'),
            'se': info.get('se'), 'n': n,
            'pi_band': [[x, lo * wf_overall, hi * wf_overall]
                        for x, lo, hi in info.get('pi_band', [])],
            'extrapolation': info.get('extrapolation', False),
            'x_min': info.get('x_min'), 'x_max': info.get('x_max'),
            'outliers': info.get('outliers', []),
            'residuals': info.get('residuals', []),
            'history_x': [c['area'] for c in cases],
            'history_y': [c['esc_settle'] for c in cases],
            'warning': reg_warning,
        }

    # ── 方法 C：分項組合法（各大類加權單價 × 結構係數）──
    m_comp = None
    t_struct = (target_conds.get('struct_type') or '').upper()
    cat_pps = {}   # 大類 → [(esc 單價, weight, 來源結構型式), ...]
    for c in cases:
        bg = c['snap'].get(cat_field, {})
        if isinstance(bg, str):
            try: bg = json.loads(bg)
            except Exception: bg = {}
        if not isinstance(bg, dict) or not bg:
            continue
        for cat, amt in bg.items():
            v = amt
            if isinstance(v, dict):  # 假設工程 items: {'settlement': x}
                v = v.get('settlement', 0)
            if not isinstance(v, (int, float)) or v <= 0:
                continue
            cat_pps.setdefault(cat, []).append(
                (v * c['esc_factor'] / c['area'], c['weight'],
                 (c['struct_type'] or '').upper()))
    comp_n = len({i for cat in cat_pps for i in range(len(cat_pps[cat]))})
    if cat_pps:
        items = []
        total_pp = 0.0
        for cat, rows in sorted(cat_pps.items()):
            vals, wts = [], []
            for pp, w, s_struct in rows:
                # 結構工程：依結構型式係數調整到目標型式
                if (kind == 'cost' and cat == STRUCT_CAT and t_struct
                        and t_struct in STRUCT_FACTORS):
                    src = STRUCT_FACTORS.get(s_struct, STRUCT_FACTORS.get('RC'))
                    pp = pp * STRUCT_FACTORS[t_struct] / src
                vals.append(pp); wts.append(w)
            cat_pp = weighted_quantile(vals, wts, 0.5) or 0
            # What-if：鋼筋/混凝土打在結構工程，工資打在全體
            if whatif and kind == 'cost' and cat == STRUCT_CAT:
                cat_pp *= 1 + (WHATIF_REBAR_IN_STRUCT * whatif.get('rebar', 0) +
                               WHATIF_CONCRETE_IN_STRUCT * whatif.get('concrete', 0)) / 100
            if whatif:
                cat_pp *= 1 + WHATIF_LABOR_OF_TOTAL * whatif.get('labor', 0) / 100
            items.append({'name': cat, 'per_ping': cat_pp,
                          'amount': cat_pp * target_area, 'n': len(rows)})
            total_pp += cat_pp
        if total_pp > 0:
            spread = (p80 - p20) / p50 if (p50 and p80 and p20) else 0.3
            m_comp = {
                'predicted': total_pp * target_area,
                'low': total_pp * target_area * (1 - spread / 2),
                'high': total_pp * target_area * (1 + spread / 2),
                'per_ping': total_pp,
                'items': sorted(items, key=lambda i: -i['amount']),
                'struct_factor_applied': bool(t_struct and t_struct in STRUCT_FACTORS),
            }

    # ── 綜合：依可靠度加權 ──
    blend = []
    if m_unit:
        blend.append(('unit_price', BLEND_W_UNIT * min(1.0, n / 3), m_unit))
    if m_reg and n >= 3:
        rq = max(0.0, (m_reg['r2_adj'] if m_reg['r2_adj'] is not None else m_reg['r2']) or 0)
        w = BLEND_W_REG * rq * min(1.0, n / 5)
        if reg_warning:
            w *= NEG_SLOPE_PENALTY
        blend.append(('regression', w, m_reg))
    if m_comp:
        blend.append(('component', BLEND_W_COMP * min(1.0, n / 3), m_comp))

    tw = sum(w for _, w, _ in blend) or 1.0
    blended_pred = sum(w * m['predicted'] for _, w, m in blend) / tw
    blended_low = sum(w * m['low'] for _, w, m in blend) / tw
    blended_high = sum(w * m['high'] for _, w, m in blend) / tw

    # 各法一致性（最大偏離綜合值的百分比）
    devs = [abs(m['predicted'] - blended_pred) / blended_pred
            for _, _, m in blend if blended_pred > 0]
    agreement = max(devs) if devs else 0

    # 信心等級：樣本數 + 方法一致性 + 回歸品質
    if n < 3:
        conf, note = 'minimal', f'樣本僅 {n} 筆，僅供參考'
    elif agreement <= 0.10 and n >= 5:
        conf, note = 'high', '三法收斂（偏差 ≤10%）且樣本充足'
    elif agreement <= 0.15:
        conf, note = 'mid', f'方法間最大偏差 {agreement*100:.0f}%'
    else:
        conf, note = 'low', f'方法間最大偏差 {agreement*100:.0f}%，建議人工覆核樣本品質'
    extra_notes = []
    if reg_warning:
        extra_notes.append(reg_warning)
    if m_reg and m_reg.get('extrapolation'):
        extra_notes.append('目標面積超出歷史樣本範圍（外插）')
    if n < 5:
        extra_notes.append(f'樣本數 {n} 筆偏少，建議補充同類案例')

    return {
        'methods': {
            'unit_price': m_unit,
            'regression': m_reg,
            'component': m_comp,
        },
        'blend_weights': {k: round(w / tw, 3) for k, w, _ in blend},
        'blended': {'predicted': blended_pred, 'low': blended_low,
                    'high': blended_high,
                    'per_ping': blended_pred / target_area if target_area else 0},
        'cases': [{k: v for k, v in c.items() if k != 'snap'} for c in cases],
        'escalation': {'enabled': escalate, 'base_date': base_date},
        'struct_share': struct_share,
        'whatif_factor': wf_overall,
        'confidence': conf,
        'confidence_note': '；'.join([note] + extra_notes),
        'n': n,
    }
