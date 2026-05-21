# -*- coding: utf-8 -*-
"""core/areas.py 單元測試"""
import pytest
from unittest.mock import patch
from pathlib import Path

import core.areas as areas_mod
from core.areas import load_areas, save_areas, sync_area


@pytest.fixture(autouse=True)
def temp_area_file(tmp_path):
    test_file = tmp_path / 'test_areas.json'
    with patch.object(areas_mod, 'AREA_FILE', test_file):
        yield test_file


class TestAreas:
    def test_load_empty(self):
        assert load_areas() == {}

    def test_save_and_load(self):
        save_areas({'AP7P1': 15000, 'AP6B': 8000})
        a = load_areas()
        assert a['AP7P1'] == 15000
        assert a['AP6B'] == 8000

    def test_sync_updates(self):
        areas = {}
        changed = sync_area('NEW', 12000, areas)
        assert changed is True
        assert areas['NEW'] == 12000

    def test_sync_no_change(self):
        areas = {'X': 5000}
        changed = sync_area('X', 5000, areas)
        assert changed is False

    def test_sync_zero_ignored(self):
        areas = {}
        changed = sync_area('Z', 0, areas)
        assert changed is False
        assert 'Z' not in areas
