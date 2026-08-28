@echo off
setlocal
cd /d "%~dp0"
python scripts\run.py
if errorlevel 1 pause
