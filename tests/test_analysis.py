# -*- coding: utf-8 -*-
"""core/analysis.py 單元測試"""
import pytest
from core.analysis import regression, render_breakdown_ratios, render_assumption_ratios


class TestRegression:
    def test_perfect_linear(self):
        pts = [(100, 1000), (200, 2000), (300, 3000)]
        pred, r2, info = regression(pts, 250)
        assert pred == pytest.approx(2500, rel=0.01)
        assert r2 == pytest.approx(1.0, rel=0.001)
        assert info['n'] == 3

    def test_two_points(self):
        pts = [(100, 500), (200, 1000)]
        pred, r2, info = regression(pts, 150)
        assert pred == pytest.approx(750, rel=0.01)
        assert r2 == pytest.approx(1.0)
        assert info['se'] == 0  # 2 points → no SE

    def test_insufficient_data(self):
        pts = [(100, 500)]
        pred, r2, info = regression(pts, 150)
        assert pred is None
        assert r2 is None
        assert info['n'] == 1

    def test_empty(self):
        pred, r2, info = regression([], 100)
        assert pred is None
        assert info['n'] == 0

    def test_non_negative(self):
        """預測值不應為負"""
        pts = [(100, 100), (200, 50)]
        pred, r2, info = regression(pts, 500)
        assert pred >= 0

    def test_info_fields(self):
        pts = [(100, 1000), (200, 2000), (300, 2800)]
        pred, r2, info = regression(pts, 250)
        assert 'a' in info  # slope
        assert 'b' in info  # intercept
        assert 'se' in info
        assert 'x' in info
        assert 'y' in info
        assert len(info['x']) == 3


class TestBreakdownRatios:
    def test_normal(self):
        snaps = [
            {'area_ping': 1000, 'total_settle': 10000,
             'big_groups': {'A': 6000, 'B': 4000}},
            {'area_ping': 2000, 'total_settle': 20000,
             'big_groups': {'A': 10000, 'B': 10000}},
        ]
        ratios = render_breakdown_ratios(snaps)
        assert ratios['A'] == pytest.approx(0.55, rel=0.01)  # avg(0.6, 0.5)
        assert ratios['B'] == pytest.approx(0.45, rel=0.01)  # avg(0.4, 0.5)

    def test_no_area(self):
        snaps = [{'area_ping': 0, 'total_settle': 10000, 'big_groups': {'A': 10000}}]
        ratios = render_breakdown_ratios(snaps)
        assert ratios == {}

    def test_empty(self):
        assert render_breakdown_ratios([]) == {}


class TestAssumptionRatios:
    def test_normal(self):
        from core.constants import ORDER
        items = {n: {'settlement': 1000} for n in ORDER}
        snaps = [{'area_ping': 1000, 'total_settle': 13000, 'items': items}]
        ratios = render_assumption_ratios(snaps)
        for n in ORDER:
            assert ratios[n] == pytest.approx(1000/13000, rel=0.01)

    def test_empty(self):
        assert render_assumption_ratios([]) == {}
