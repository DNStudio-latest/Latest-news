@echo off
cd /d "%~dp0"
title Job Agent - Update
git pull
python -m pip install -q -r requirements.txt
echo.
echo Updated.
pause
