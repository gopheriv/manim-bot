@echo off
title Manim Animation Bot
cd /d "%~dp0"
echo [%date% %time%] Starting Manim Animation Bot...
python bot.py
echo [%date% %time%] Bot exited with code %errorlevel%
pause
