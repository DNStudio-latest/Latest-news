@echo off
cd /d "%~dp0"
title Job Agent - Review
start "" notepad "output\queue\README.md"
python run.py review
echo.
pause
