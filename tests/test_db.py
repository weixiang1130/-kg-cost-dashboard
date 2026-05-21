# -*- coding: utf-8 -*-
"""core/db.py 單元測試 — 使用臨時資料庫"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

import core.db as db_mod
from core.db import (
    init_db, db_insert_assumption, db_get_assumption_snaps,
    db_get_all_assumption_names, db_insert_cost, db_get_cost_snaps,
    db_get_all_cost_names, db_check_duplicate, db_delete_snapshot,
    db_get_by_type, db_get_type_counts,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """每個測試用獨立的臨時 DB"""
    test_db = tmp_path / 'test.db'
    with patch.object(db_mod, 'DB_FILE', test_db):
        init_db()
        yield test_db


class TestAssumptionCRUD:
    def test_insert_and_get(self):
        items = {'租工': {'budget': 100, 'settlement': 200}}
        db_insert_assumption('AP7P1', '台積電AP7P1-FAB', '2026/03/31',
                            1000, 500, 800, items, 'test.xlsx',
                            file_date='2026-03-31', project_type='FAB')
        snaps = db_get_assumption_snaps('AP7P1')
        assert len(snaps) == 1
        s = snaps[0]
        assert s['display_name'] == 'AP7P1'
        assert s['total_settle'] == 800
        assert s['items']['租工']['settlement'] == 200
        assert s['project_type'] == 'FAB'

    def test_get_all_names(self):
        db_insert_assumption('AAA', '', '', 0, 0, 0, {}, '')
        db_insert_assumption('BBB', '', '', 0, 0, 0, {}, '')
        db_insert_assumption('AAA', '', '', 0, 0, 0, {}, '', file_date='2026-04-01')
        names = db_get_all_assumption_names()
        assert names == ['AAA', 'BBB']

    def test_duplicate_check(self):
        db_insert_assumption('X', '', '', 0, 0, 0, {}, '', file_date='2026-01-01')
        assert db_check_duplicate('assumption_snapshots', 'X', '2026-01-01') is True
        assert db_check_duplicate('assumption_snapshots', 'X', '2026-01-02') is False
        assert db_check_duplicate('assumption_snapshots', 'Y', '2026-01-01') is False


class TestCostCRUD:
    def test_insert_and_get(self):
        db_insert_cost('AP6B', '台積電', 500, 1650, 9999,
                      {'A': 5000, 'B': 4999}, [], 0, 'src.xlsx',
                      b'exceldata', 'out.xlsx',
                      file_date='2026-04-01', project_type='CUP')
        snaps = db_get_cost_snaps('AP6B')
        assert len(snaps) == 1
        assert snaps[0]['total_settle'] == 9999
        assert snaps[0]['big_groups']['A'] == 5000

    def test_all_names(self):
        db_insert_cost('P1', '', 0, 0, 0, {}, [], 0, '', b'', '')
        db_insert_cost('P2', '', 0, 0, 0, {}, [], 0, '', b'', '')
        assert db_get_all_cost_names() == ['P1', 'P2']


class TestDeleteAndTypeCounts:
    def test_delete(self):
        db_insert_assumption('DEL', '', '', 0, 0, 0, {}, '')
        snaps = db_get_assumption_snaps('DEL')
        assert len(snaps) == 1
        db_delete_snapshot('assumption_snapshots', snaps[0]['id'])
        assert len(db_get_assumption_snaps('DEL')) == 0

    def test_type_counts(self):
        db_insert_assumption('A', '', '', 0, 0, 0, {}, '', project_type='FAB')
        db_insert_assumption('B', '', '', 0, 0, 0, {}, '', project_type='FAB')
        db_insert_cost('C', '', 0, 0, 0, {}, [], 0, '', b'', '', project_type='CUP')
        a_counts, c_counts = db_get_type_counts()
        assert a_counts.get('FAB', 0) == 2
        assert c_counts.get('CUP', 0) == 1

    def test_get_by_type(self):
        db_insert_assumption('F1', '', '', 0, 0, 100, {}, '', project_type='FAB')
        db_insert_assumption('F2', '', '', 0, 0, 200, {}, '', project_type='CUP')
        fab = db_get_by_type('assumption_snapshots', 'FAB')
        assert len(fab) == 1
        assert fab[0]['total_settle'] == 100


class TestConditionsJson:
    def test_conditions_stored(self):
        cond = {'fab_code': 'AP7P1', 'region': '竹科', 'rebar_price': 28000}
        db_insert_assumption('C1', '', '', 0, 0, 0, {}, '',
                            conditions=cond, project_type='FAB')
        snaps = db_get_assumption_snaps('C1')
        assert snaps[0]['conditions']['fab_code'] == 'AP7P1'
        assert snaps[0]['conditions']['rebar_price'] == 28000

    def test_empty_conditions(self):
        db_insert_assumption('C2', '', '', 0, 0, 0, {}, '')
        snaps = db_get_assumption_snaps('C2')
        assert snaps[0]['conditions'] == {}
