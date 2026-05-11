@echo off
chcp 65001 >nul 2>nul
title Cost Management System

echo ============================================
echo   Cost Management Automation System v8
echo   (Local Mode - No deployment needed)
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b
)

echo [1/3] Checking Python...
python --version
echo.

echo [2/3] Installing packages (first run takes 1-2 min)...
pip install streamlit openpyxl lxml plotly pandas xlrd --quiet 2>nul
echo Done.
echo.

if not exist "kg_data" mkdir kg_data

echo [3/3] Starting dashboard...
echo.
echo ============================================
echo   Dashboard URL: http://localhost:8501
echo.
echo   Browser will open automatically.
echo   If not, copy URL above to your browser.
echo.
echo   Press Ctrl+C in this window to STOP.
echo ============================================
echo.

streamlit run kg_dashboard.py --server.headless=false --server.port=8501

pause
