@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Pass the script directory explicitly so Python never reconstructs a
rem broken absolute path when the Windows username contains spaces.
set "DANA_ROOT=%~dp0"
set "DANA_ROOT=%DANA_ROOT:~0,-1%"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    py -3 scripts/run.py %*
    exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    python scripts/run.py %*
    exit /b %ERRORLEVEL%
)

echo Dana Python runtime was not found.
echo Run the Dana installer first.
exit /b 1
