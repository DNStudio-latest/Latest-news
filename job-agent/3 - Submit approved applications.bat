@echo off
cd /d "%~dp0"
title Job Agent - Submit
echo Only items YOU approved will be shown. You will be asked yes or no for each one.
echo.
python run.py submit
echo.
pause
