@echo off
chcp 65001 >nul
echo ========================================
echo   KG 成本管理 API Server
echo   http://localhost:8000
echo   API 文件：http://localhost:8000/docs
echo ========================================
echo.
cd /d "%~dp0"
uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
pause
