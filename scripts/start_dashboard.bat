@echo off
rem AI-DAX Lite - Windows Dashboard Launcher
cd /d "%~dp0\.."

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

echo Starting AI-DAX Lite Stack...
start /B python -m aidax.workload
start /B python -m aidax.scheduler
echo Starting web server on http://localhost:8000...
python -m uvicorn aidax.api:app --host 0.0.0.0 --port 8000
