@echo off
cd /d "%~dp0"
start /b pythonw manim_bot_watchdog.py
echo [%date% %time%] Manim Bot watchdog started in background (pythonw)
