# -*- coding: utf-8 -*-
"""core/conditions.py 單元測試"""
import pytest
from core.conditions import detect_project_type, detect_fab_code, detect_region, default_conditions


class TestDetectProjectType:
    def test_fab(self):
        assert detect_project_type('AP7P1-FAB') == 'FAB'
        assert detect_project_type('台積電FAB棟') == 'FAB'
        assert detect_project_type('fab-test') == 'FAB'

    def test_cup(self):
        assert detect_project_type('AP6B-CUP') == 'CUP'
        assert detect_project_type('CUP棟') == 'CUP'

    def test_office(self):
        assert detect_project_type('OFFICE-A棟') == 'OFFICE'

    def test_logistics(self):
        assert detect_project_type('台積電物流中心') == '物流中心'

    def test_other(self):
        assert detect_project_type('未知建案') == '其他'
        assert detect_project_type('') == '其他'


class TestDetectFabCode:
    def test_ap_pattern(self):
        assert detect_fab_code('台積電AP7P1-FAB') == 'AP7P1'
        assert detect_fab_code('AP6B-CUP') == 'AP6B'

    def test_f_pattern(self):
        assert detect_fab_code('F22P5-FAB') == 'F22P5'

    def test_no_match(self):
        assert detect_fab_code('台積電辦公室') == ''
        assert detect_fab_code('') == ''


class TestDetectRegion:
    def test_south(self):
        assert detect_region('南科AP7P1') == '南科'

    def test_central(self):
        assert detect_region('中科F22') == '中科'

    def test_hsinchu(self):
        assert detect_region('竹科AP6B') == '竹科'
        assert detect_region('寶山廠') == '竹科'
        assert detect_region('新竹CUP') == '竹科'

    def test_unknown(self):
        assert detect_region('某工地') == ''


class TestDefaultConditions:
    def test_has_all_keys(self):
        c = default_conditions()
        expected_keys = {'fab_code', 'region', 'struct_type', 'floors',
                        'duration_months', 'contract_mode', 'with_material',
                        'with_equipment', 'rebar_price', 'concrete_price',
                        'formwork_price', 'price_index', 'note'}
        assert set(c.keys()) == expected_keys

    def test_all_empty(self):
        c = default_conditions()
        for k, v in c.items():
            assert v == '' or v == 0, f"{k} should be empty/zero, got {v}"
