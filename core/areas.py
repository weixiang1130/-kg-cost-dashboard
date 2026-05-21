# -*- coding: utf-8 -*-
"""面積設定管理"""
import json
from .constants import AREA_FILE


def load_areas() -> dict:
    if AREA_FILE.exists():
        with open(AREA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_areas(a: dict):
    with open(AREA_FILE, 'w', encoding='utf-8') as f:
        json.dump(a, f, ensure_ascii=False, indent=2)


def sync_area(dn: str, ping: float, areas: dict) -> bool:
    """同步面積到 areas dict 並存檔，回傳是否有更新"""
    if ping > 0 and abs(areas.get(dn, 0) - ping) > 0.001:
        areas[dn] = ping
        save_areas(areas)
        return True
    return False
