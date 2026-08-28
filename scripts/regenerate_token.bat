@echo off
setlocal
cd /d "%~dp0.."
python scripts\regenerate_token.py
if errorlevel 1 exit /b %errorlevel%
echo Restart Dana after regenerating the token.
