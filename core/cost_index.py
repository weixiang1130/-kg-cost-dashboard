# -*- coding: utf-8 -*-
"""營造工程物價指數（CCI）— 歷史結算金額調整到投標基準日

預設值參考行政院主計總處「營造工程物價總指數」年平均（2021=100 近似值），
僅為內建估計，實際投標前應以最新公告值校正（GET/PUT /api/cost-index）。
"""
import json
from pathlib import Path

INDEX_FILE = Path("./cost_index.json")

# 預設年指數（2021=100 基準的近似值；2025/2026 為推估）
DEFAULT_INDEX = {
    "2018": 93.0,
    "2019": 95.3,
    "2020": 96.5,
    "2021": 107.3,
    "2022": 114.7,
    "2023": 117.5,
    "2024": 121.0,
    "2025": 124.0,
    "2026": 126.5,
}


def load_index() -> dict:
    """讀取物價指數表（檔案不存在時用內建預設值）"""
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data:
                return {str(k): float(v) for k, v in data.items()}
        except Exception:
            pass
    return dict(DEFAULT_INDEX)


def save_index(data: dict):
    clean = {str(k): float(v) for k, v in data.items() if float(v) > 0}
    INDEX_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                          encoding='utf-8')


def _year_index(idx: dict, year: int) -> float:
    """取某年指數；超出範圍時取最近一年（不外推）"""
    ys = sorted(int(y) for y in idx)
    if not ys:
        return 100.0
    y = min(max(year, ys[0]), ys[-1])
    return idx[str(y)]


def escalation_factor(from_date: str, to_date: str, idx: dict = None) -> float:
    """物價調整係數：from_date 的金額 × factor = to_date 的等值金額
    日期格式 'YYYY-MM-DD' 或 'YYYY'；解析失敗回傳 1.0
    """
    idx = idx or load_index()

    def _year(s):
        try:
            return int(str(s)[:4])
        except (ValueError, TypeError):
            return None

    fy, ty = _year(from_date), _year(to_date)
    if fy is None or ty is None or fy == ty:
        return 1.0
    base = _year_index(idx, fy)
    target = _year_index(idx, ty)
    if base <= 0:
        return 1.0
    return target / base
