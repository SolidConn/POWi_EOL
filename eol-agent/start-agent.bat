@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM EOL jig agent launcher. Double-click to start, or let it auto-start at login
REM (see install-autostart.bat). Keep this window open while testing — closing
REM it stops the agent. It auto-restarts if the agent ever crashes.
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"
title EOL Jig Agent

REM Verify Python is reachable (double-click launches don't always inherit PATH).
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo   ERROR: 'python' is not on PATH for this window.
  echo   Install Python 3.11+ ^(python.org / Microsoft Store^) and reopen this launcher.
  echo.
  pause
  exit /b 1
)

REM Don't start a second copy — if 9151 is already bound, the agent is up.
netstat -ano | findstr ":9151" | findstr /i "LISTENING" >nul
if not errorlevel 1 (
  echo.
  echo   EOL jig agent is already running ^(port 9151 in use^). Nothing to do.
  timeout /t 3 >nul
  exit /b 0
)

:loop
echo.
echo Starting EOL jig agent...  (close this window to stop it)
python agent.py
echo.
echo Agent exited. Restarting in 3s...  (close this window to stop)
timeout /t 3 >nul
goto loop
