@echo off
cd /d "%~dp0"
if exist output\queue start "" explorer "output\queue"
if exist output\results.md start "" notepad "output\results.md"
