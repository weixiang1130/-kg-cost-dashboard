@echo off
echo ========================================
echo   KG Cost Management API Server
echo   http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ========================================
echo.
cd /d "%~dp0"
echo Starting server...
echo.
python -m uvicorn api_server:app --reload --host 127.0.0.1 --port 8000
echo.
echo ========================================
echo   Server stopped.
echo ========================================
pause
