# -*- coding: utf-8 -*-
"""大宗物料參考行情表 — What-if 試算的價格錨點

內建值為台灣市場近似參考價（非即時行情），實際使用請以下列公開來源校正：
  - 鋼筋：豐興鋼鐵每週牌價、中鋼盤價（SD420W 竹節鋼筋）
  - 預拌混凝土：各區拌合廠報價（3000psi 常用規格）
  - 營造工資：主計總處營造工程物價指數（勞務類）月報
更新方式：GET/PUT /api/material-prices，或直接編輯 material_prices.json
"""
import json
from pathlib import Path

PRICES_FILE = Path("./material_prices.json")

# 年度參考價（內建近似值；2025/2026 為推估）
DEFAULT_PRICES = {
    # 鋼筋 元/噸（SD420W）
    "rebar": {
        "2018": 19000, "2019": 18500, "2020": 17500,
        "2021": 24000, "2022": 25500, "2023": 21500,
        "2024": 20500, "2025": 19500, "2026": 19000,
    },
    # 預拌混凝土 元/m³（3000psi）
    "concrete": {
        "2018": 1900, "2019": 2000, "2020": 2050,
        "2021": 2200, "2022": 2500, "2023": 2700,
        "2024": 2850, "2025": 2900, "2026": 2950,
    },
}

MATERIAL_UNITS = {'rebar': '元/噸', 'concrete': '元/m³'}
MATERIAL_NAMES = {'rebar': '鋼筋', 'concrete': '預拌混凝土'}


def load_prices() -> dict:
    """讀取參考行情表（檔案不存在時用內建預設值）"""
    if PRICES_FILE.exists():
        try:
            data = json.loads(PRICES_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict) and data:
                out = {}
                for mat, table in data.items():
                    if isinstance(table, dict):
                        out[mat] = {str(k): float(v) for k, v in table.items()}
                if out:
                    return out
        except Exception:
            pass
    return {m: dict(t) for m, t in DEFAULT_PRICES.items()}


def save_prices(data: dict):
    clean = {}
    for mat, table in data.items():
        if not isinstance(table, dict):
            continue
        rows = {str(k): float(v) for k, v in table.items() if float(v) > 0}
        if rows:
            clean[mat] = rows
    PRICES_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                           encoding='utf-8')


def reference_price(material: str, year, prices: dict = None) -> float:
    """取某材料某年的參考價；超出範圍取最近一年，無資料回 0"""
    prices = prices or load_prices()
    table = prices.get(material, {})
    if not table:
        return 0.0
    ys = sorted(int(y) for y in table)
    try:
        y = int(str(year)[:4])
    except (ValueError, TypeError):
        y = ys[-1]
    y = min(max(y, ys[0]), ys[-1])
    return table[str(y)]


def price_delta_pct(material: str, input_price: float, base_year,
                    prices: dict = None) -> float:
    """輸入實際發包價 → 相對今日參考行情的偏差 %（What-if 傳導用）
    input_price <= 0 視為未輸入，回 0
    """
    if not input_price or input_price <= 0:
        return 0.0
    ref = reference_price(material, base_year, prices)
    if ref <= 0:
        return 0.0
    return (input_price - ref) / ref * 100
