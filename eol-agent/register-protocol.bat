@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM Register the powi-eol:// URL protocol on THIS PC, so the "Start agent" button
REM on the /eol page can launch the jig agent (a web page can't spawn a local
REM process directly). Per-user (HKCU), no admin, reversible.
REM   register-protocol.bat          → enable the button
REM   register-protocol.bat remove   → disable it
REM ─────────────────────────────────────────────────────────────────────────
set "KEY=HKCU\Software\Classes\powi-eol"
set "BAT=%~dp0start-agent.bat"

if /i "%~1"=="remove" (
  reg delete "%KEY%" /f >nul 2>nul && echo powi-eol:// protocol removed. || echo Protocol was not registered.
  pause & exit /b 0
)

reg add "%KEY%" /ve /d "URL:POWi EOL" /f >nul
reg add "%KEY%" /v "URL Protocol" /d "" /f >nul
REM Launch the agent in its own window; the guard in start-agent.bat prevents duplicates.
reg add "%KEY%\shell\open\command" /ve /d "cmd /c start \"EOL Jig Agent\" \"%BAT%\"" /f >nul

if errorlevel 1 ( echo FAILED to register the protocol. ) else ( echo powi-eol:// registered. The "Start agent" button on the /eol page now works on this PC. )
pause
