# -*- coding: utf-8 -*-
"""通用工具函式"""
import os
import re
import sys
import importlib
import importlib.util
from datetime import datetime
from pathlib import Path


def parse_date_str(s) -> str | None:
    """從任意字串中擷取 YYYY-MM-DD，找不到回傳 None"""
    if not s: return None
    m = re.search(r'(\d{4})[-/\.](\d{2})[-/\.](\d{2})', str(s))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def extract_file_date(fp, cutoff_fallback=None) -> str:
    """日期優先順序：① 檔名內的日期 → ② 檔案內截止日 → ③ 今天"""
    d = parse_date_str(os.path.basename(str(fp)))
    if d: return d
    d = parse_date_str(cutoff_fallback)
    if d: return d
    return datetime.now().strftime('%Y-%m-%d')


def extract_name_from_filename(fp) -> str | None:
    """從檔名括號內取專案名稱（非日期內容）"""
    fn = re.sub(r'\.xlsx?$', '', os.path.basename(str(fp)), flags=re.IGNORECASE)
    m = re.search(r'[（(]([^）)]+)[）)]', fn)
    if m:
        content = m.group(1).strip()
        if not parse_date_str(content):
            return content
    return None


def clean_project_name(name) -> str | None:
    """清理從檔案內部讀取的專案名稱（B2 欄）"""
    if not name or name.strip() in ('', '未知專案'):
        return None
    return name.strip()[:40]


def extract_display_name(fp) -> str:
    """最終備用：從檔名推測顯示名稱"""
    fn = os.path.basename(str(fp))
    fn = re.sub(r'\.xlsx?$', '', fn, flags=re.IGNORECASE)
    fn = re.sub(r'^KG.*一覽表[_\s]*', '', fn)
    fn = re.sub(r'[_\s]*\d{4}[-\.]\d{2}[-\.]\d{2}[_\s]*$', '', fn)
    return fn.strip('_ ()（）') or os.path.basename(str(fp))


def fmt(n) -> str:
    """格式化金額（億/萬/逗號）"""
    if n is None or n == 0: return '-'
    if abs(n) >= 1e8: return f"{n/1e8:.2f}億"
    if abs(n) >= 1e4: return f"{n/1e4:,.0f}萬"
    return f"{n:,.0f}"


def fpp(n, p) -> str:
    """格式化元/坪"""
    if not n or not p or p < 10: return '-'
    return f"{n/p:,.0f}"


def load_v14_module():
    """載入 kg_cost_analysis_v14.py 模組"""
    try:
        sd = Path(__file__).parent.parent
    except NameError:
        sd = Path('.')
    for p in [sd / 'kg_cost_analysis_v14.py', Path('.') / 'kg_cost_analysis_v14.py']:
        if p.exists():
            spec = importlib.util.spec_from_file_location("v14", str(p))
            mod = importlib.util.module_from_spec(spec)
            old = sys.argv
            sys.argv = ['']
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.argv = old
            return mod
    return None
