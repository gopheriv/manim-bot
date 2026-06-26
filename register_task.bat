@echo off
echo ============================================
echo  Manim Bot - Register Scheduled Task
echo  Run this as Administrator!
echo ============================================
echo.

:: Get the directory where this script lives
set "BOT_DIR=%~dp0"
set "PYTHON_EXE=C:\Python314\pythonw.exe"
set "SCRIPT=%BOT_DIR%manim_bot_watchdog.py"

schtasks /create ^
  /tn "Manim Animation Bot" ^
  /tr "\"%PYTHON_EXE%\" \"%SCRIPT%\"" ^
  /sc onlogon ^
  /rl highest ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Scheduled task "Manim Animation Bot" created.
    echo      It will start on every user login.
) else (
    echo.
    echo [FAIL] Could not create task. Run this script as Administrator.
)

echo.
pause
