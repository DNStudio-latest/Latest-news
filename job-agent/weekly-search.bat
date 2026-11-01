@echo off
cd /d "%~dp0"
python run.py run >> logs\weekly.log 2>&1
