@echo off
cd /d "%~dp0"
echo This makes Windows search for jobs every Monday at 9 AM.
echo It only searches and prepares. It never submits anything.
echo.
set /p OK=Turn it on? (yes / no): 
if /i not "%OK%"=="yes" (echo Cancelled. & pause & exit /b)
schtasks /create /tn "JobAgentWeeklySearch" /sc weekly /d MON /st 09:00 /tr "%~dp0weekly-search.bat" /f
echo.
echo Done. To stop it, double-click "Turn OFF weekly search.bat".
pause
