# -*- coding: utf-8 -*-
"""core/utils.py 單元測試"""
import pytest
from core.utils import parse_date_str, extract_name_from_filename, clean_project_name, extract_display_name, fmt, fpp


class TestParseDateStr:
    def test_dash(self):
        assert parse_date_str('2026-04-24') == '2026-04-24'

    def test_slash(self):
        assert parse_date_str('2026/03/31') == '2026-03-31'

    def test_dot(self):
        assert parse_date_str('2026.05.11') == '2026-05-11'

    def test_embedded(self):
        assert parse_date_str('KG一覽表 (2026-04-24).xlsx') == '2026-04-24'

    def test_none(self):
        assert parse_date_str(None) is None
        assert parse_date_str('') is None
        assert parse_date_str('no date here') is None


class TestExtractNameFromFilename:
    def test_project_name(self):
        assert extract_name_from_filename('KG一覽表 (AP7P1-FAB).xlsx') == 'AP7P1-FAB'

    def test_date_returns_none(self):
        assert extract_name_from_filename('KG一覽表 (2026-04-24).xlsx') is None

    def test_no_parens(self):
        assert extract_name_from_filename('KG一覽表.xlsx') is None

    def test_fullwidth_parens(self):
        assert extract_name_from_filename('KG一覽表（AP6B-CUP）.xlsx') == 'AP6B-CUP'


class TestCleanProjectName:
    def test_normal(self):
        assert clean_project_name('台積電AP7P1-FAB') == '台積電AP7P1-FAB'

    def test_trim(self):
        assert clean_project_name('  台積電  ') == '台積電'

    def test_too_long(self):
        name = 'A' * 50
        result = clean_project_name(name)
        assert len(result) == 40

    def test_empty(self):
        assert clean_project_name('') is None
        assert clean_project_name('未知專案') is None
        assert clean_project_name(None) is None


class TestFmt:
    def test_zero(self):
        assert fmt(0) == '-'
        assert fmt(None) == '-'

    def test_wan(self):
        assert fmt(1234567) == '123萬'

    def test_yi(self):
        assert fmt(123456789) == '1.23億'

    def test_small(self):
        assert fmt(999) == '999'

    def test_negative_wan(self):
        result = fmt(-500000)
        assert '50' in result and '萬' in result


class TestFpp:
    def test_normal(self):
        assert fpp(1000000, 100) == '10,000'

    def test_no_area(self):
        assert fpp(1000000, 0) == '-'
        assert fpp(1000000, 5) == '-'

    def test_no_value(self):
        assert fpp(0, 100) == '-'
        assert fpp(None, 100) == '-'
