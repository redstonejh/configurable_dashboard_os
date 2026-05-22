@echo off
cd /d "%~dp0"
echo Starting Configurable Dashboard Skeleton...
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
