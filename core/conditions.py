# -*- coding: utf-8 -*-
"""專案條件偵測與預設值"""
import re


def detect_project_type(name: str) -> str:
    s = str(name).upper()
    if 'FAB' in s: return 'FAB'
    if 'CUP' in s: return 'CUP'
    if 'OFFICE' in s: return 'OFFICE'
    if '物流' in str(name): return '物流中心'
    return '其他'


def detect_fab_code(name: str) -> str:
    """從專案名偵測廠區代號，如 AP7P1、F22P5、AP6B 等"""
    s = str(name).upper()
    m = re.search(r'(AP\d+[A-Z]?\d*|F\d+P?\d*)', s)
    return m.group(1) if m else ''


def detect_region(name: str) -> str:
    """從專案名猜測地區"""
    s = str(name)
    if '南科' in s: return '南科'
    if '中科' in s: return '中科'
    if '竹科' in s or '寶山' in s or '新竹' in s: return '竹科'
    return ''


def default_conditions() -> dict:
    """回傳空白的條件字典"""
    return {
        'fab_code': '', 'region': '', 'struct_type': '',
        'floors': 0, 'duration_months': 0,
        'contract_mode': '', 'with_material': '', 'with_equipment': '',
        'rebar_price': 0, 'concrete_price': 0, 'formwork_price': 0,
        'price_index': 0, 'note': '',
    }
