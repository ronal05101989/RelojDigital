@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Control de asistencia
if not exist .venv (
    echo Preparando el programa por primera vez...
    python -m venv .venv || (echo. & echo Falta instalar Python: https://www.python.org/downloads/ & pause & exit /b 1)
    .venv\Scripts\python -m pip install --upgrade pip >nul
    .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
start "" http://localhost:5000
.venv\Scripts\python app.py
pause
