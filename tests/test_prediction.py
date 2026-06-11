# -*- coding: utf-8 -*-
"""core/prediction.py 三法預估引擎測試"""
import pytest
from core.prediction import (ensemble_predict, similarity_weight,
                             weighted_quantile, STRUCT_FACTORS)
from core.cost_index import escalation_factor, load_index, DEFAULT_INDEX


def _snap(area, settle, date='2024-06-01', conds=None, bg=None):
    return {'display_name': f'案例{area}', 'area_ping': area,
            'total_settle': settle, 'read_date': date,
            'conditions': conds or {}, 'big_groups': bg or {}}


class TestWeightedQuantile:
    def test_median_uniform(self):
        assert weighted_quantile([1, 2, 3], [1, 1, 1], 0.5) == 2

    def test_weight_dominates(self):
        # 權重極端時中位數偏向高權重值
        assert weighted_quantile([100, 200], [0.01, 10], 0.5) == 200

    def test_empty_weights(self):
        assert weighted_quantile([1, 2], [0, 0], 0.5) is None


class TestEscalation:
    def test_same_year(self):
        assert escalation_factor('2024-01-01', '2024-12-31') == 1.0

    def test_inflation_positive(self):
        # 2021 → 2024 物價上漲，係數 > 1
        f = escalation_factor('2021-06-01', '2024-06-01')
        assert f == pytest.approx(DEFAULT_INDEX['2024'] / DEFAULT_INDEX['2021'])
        assert f > 1.1

    def test_bad_date(self):
        assert escalation_factor('', '2024-01-01') == 1.0
        assert escalation_factor(None, '2024-01-01') == 1.0


class TestSimilarity:
    def test_same_conditions_full_weight(self):
        s = _snap(20000, 6e9, date='2026-01-01',
                  conds={'struct_type': 'SC', 'contract_mode': '總價承攬'})
        r = similarity_weight(s, 20000, {'struct_type': 'SC',
                                         'contract_mode': '總價承攬'}, 2026)
        assert r['factors']['area'] == pytest.approx(1.0)
        assert r['factors']['struct'] == 1.0
        assert r['factors']['contract'] == 1.0

    def test_struct_mismatch_penalized(self):
        s = _snap(20000, 6e9, conds={'struct_type': 'RC'})
        r_same = similarity_weight(_snap(20000, 6e9, conds={'struct_type': 'SC'}),
                                   20000, {'struct_type': 'SC'}, 2026)
        r_diff = similarity_weight(s, 20000, {'struct_type': 'SC'}, 2026)
        assert r_diff['weight'] < r_same['weight']

    def test_area_distance_decays(self):
        near = similarity_weight(_snap(20000, 6e9), 22000, {}, 2026)
        far = similarity_weight(_snap(5000, 2e9), 22000, {}, 2026)
        assert near['factors']['area'] > far['factors']['area']

    def test_older_decays(self):
        old = similarity_weight(_snap(20000, 6e9, date='2020-01-01'), 20000, {}, 2026)
        new = similarity_weight(_snap(20000, 6e9, date='2026-01-01'), 20000, {}, 2026)
        assert old['factors']['time'] < new['factors']['time']


class TestEnsemble:
    def _snaps(self):
        bg = lambda s: {'結構工程': s * 0.4, '裝修工程': s * 0.3, '機電工程': s * 0.3}
        return [
            _snap(10000, 3.0e9, '2023-06-01', bg=bg(3.0e9)),
            _snap(15000, 4.6e9, '2024-06-01', bg=bg(4.6e9)),
            _snap(20000, 6.1e9, '2025-06-01', bg=bg(6.1e9)),
            _snap(25000, 7.7e9, '2025-12-01', bg=bg(7.7e9)),
        ]

    def test_basic_structure(self):
        r = ensemble_predict(self._snaps(), 18000, {}, kind='cost',
                             base_date='2026-06-11')
        assert r is not None
        assert r['methods']['unit_price'] is not None
        assert r['methods']['regression'] is not None
        assert r['methods']['component'] is not None
        assert r['blended']['low'] <= r['blended']['predicted'] <= r['blended']['high']
        assert r['n'] == 4

    def test_blended_in_reasonable_range(self):
        # 單價約 30~31 萬/坪（調整後再高一些）→ 18000 坪約 55~70 億
        r = ensemble_predict(self._snaps(), 18000, {}, base_date='2026-06-11')
        assert 4.5e9 < r['blended']['predicted'] < 8e9

    def test_escalation_raises_prediction(self):
        r_esc = ensemble_predict(self._snaps(), 18000, {}, escalate=True,
                                 base_date='2026-06-11')
        r_raw = ensemble_predict(self._snaps(), 18000, {}, escalate=False,
                                 base_date='2026-06-11')
        assert r_esc['blended']['predicted'] > r_raw['blended']['predicted']

    def test_whatif_rebar_increases(self):
        base = ensemble_predict(self._snaps(), 18000, {}, base_date='2026-06-11')
        up = ensemble_predict(self._snaps(), 18000, {}, base_date='2026-06-11',
                              whatif={'rebar': 10, 'concrete': 0, 'labor': 0})
        assert up['blended']['predicted'] > base['blended']['predicted']
        # 鋼筋 +10% 傳導 = 結構佔比 0.4 × 0.45 × 10% = +1.8%
        ratio = up['blended']['predicted'] / base['blended']['predicted']
        assert ratio == pytest.approx(1.018, abs=0.005)

    def test_struct_factor_adjusts_component(self):
        # 歷史全為 RC，目標 SRC → 分項法結構工程單價 ×1.30
        snaps = [
            _snap(10000, 3.0e9, '2025-06-01', conds={'struct_type': 'RC'},
                  bg={'結構工程': 1.2e9, '裝修工程': 1.8e9}),
            _snap(20000, 6.0e9, '2025-09-01', conds={'struct_type': 'RC'},
                  bg={'結構工程': 2.4e9, '裝修工程': 3.6e9}),
            _snap(15000, 4.5e9, '2025-12-01', conds={'struct_type': 'RC'},
                  bg={'結構工程': 1.8e9, '裝修工程': 2.7e9}),
        ]
        rc = ensemble_predict(snaps, 15000, {'struct_type': 'RC'},
                              base_date='2026-01-01')
        src = ensemble_predict(snaps, 15000, {'struct_type': 'SRC'},
                               base_date='2026-01-01')
        comp_rc = rc['methods']['component']['predicted']
        comp_src = src['methods']['component']['predicted']
        # 結構工程佔 40%，係數 1.30 → 分項法總價應升約 12%
        assert comp_src / comp_rc == pytest.approx(1 + 0.4 * 0.30, abs=0.02)

    def test_negative_slope_warns(self):
        # 面積越大造價越低（異常資料）→ 回歸法應有警告
        snaps = [_snap(5000, 12e9, '2025-06-01'),
                 _snap(15000, 6e9, '2025-09-01'),
                 _snap(25000, 3e9, '2025-12-01')]
        r = ensemble_predict(snaps, 20000, {}, base_date='2026-01-01')
        assert r['methods']['regression']['warning']
        # 回歸權重應被大幅折減
        assert r['blend_weights'].get('regression', 0) < 0.3

    def test_empty(self):
        assert ensemble_predict([], 18000, {}) is None

    def test_single_sample(self):
        r = ensemble_predict([_snap(20000, 6e9, '2025-06-01')], 18000, {},
                             base_date='2026-01-01')
        assert r is not None
        assert r['methods']['regression'] is None
        assert r['confidence'] == 'minimal'
        assert r['methods']['unit_price']['predicted'] > 0
