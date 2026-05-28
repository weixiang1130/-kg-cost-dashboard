# -*- coding: utf-8 -*-
"""core — 成本管理監測系統業務邏輯模組"""
from .constants import *
from .conditions import detect_project_type, detect_fab_code, detect_region, default_conditions
from .parser import read_xlsx_via_xml, extract_categories, get_project_info
from .utils import (parse_date_str, extract_file_date, extract_name_from_filename,
                    clean_project_name, extract_display_name, fmt, fpp)
from .areas import load_areas, save_areas, sync_area
from .db import (init_db, db_insert_assumption, db_get_assumption_snaps,
                 db_get_all_assumption_names, db_insert_cost, db_get_cost_snaps,
                 db_get_all_cost_names, db_get_cost_excel, db_update_cost_area,
                 db_update_assumption_area,
                 db_delete_snapshot, db_clear_all, db_check_duplicate,
                 db_get_by_type, db_get_type_counts)
from .analysis import regression, render_breakdown_ratios, render_assumption_ratios
