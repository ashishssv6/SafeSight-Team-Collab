@echo off
title SafeSight SOC Launcher
echo Starting SafeSight Autonomous Surveillance Ecosystem...

:: Activate Virtual Environment
call .venv\Scripts\activate.bat

:: Launch SOC Dashboard in a separate window
start cmd /k "%~dp0.venv\Scripts\activate.bat" ^&^& streamlit run backend/dashboard.py

:: Launch AI Sentry Engine
python backend/safesight.py

pause
