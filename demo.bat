@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Control de asistencia (DEMO)
if not exist .venv (
    python -m venv .venv || (echo. & echo Falta instalar Python: https://www.python.org/downloads/ & pause & exit /b 1)
    .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
set ASISTENCIA_DB=demo.db
.venv\Scripts\python demo.py
start "" http://localhost:5000
.venv\Scripts\python app.py --sin-reloj
pause
