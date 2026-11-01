@echo off
cd /d "%~dp0"
title Job Agent - Searching
echo Searching for jobs. This takes a few minutes. Nothing will be sent.
echo.
python run.py run
echo.
for /f "delims=" %%f in ('dir /b /o-d output\summary-*.md 2^>nul') do (start "" notepad "output\%%f" & goto :done)
:done
echo The summary has opened in Notepad.
pause
