# -*- coding: utf-8 -*-
"""共用常數"""
from pathlib import Path

DATA_DIR = Path("./kg_data")
DB_FILE = Path("./kg_history.db")
AREA_FILE = Path("./kg_areas.json")
LOGO_FILE = Path("./logo.png")

M2_PER_PING = 3.30579
PING_PER_M2 = 0.3025

# 13 項假設工程（固定順序）
ORDER = [
    '租工', '打石工', '技術工', '零星建材', '雜項工程', '機具租金',
    '安衛零星', '雜支一', '雜支二', '水費', '電費', '電話費', '人員薪資',
]

PROJECT_TYPES = ['FAB', 'CUP', 'OFFICE', '物流中心', '其他']
REGIONS = ['竹科', '中科', '南科', '其他']
STRUCT_TYPES = ['RC', 'SC', 'SRC', '其他']
CONTRACT_MODES = ['', '點工', '包工', '連工帶料']
