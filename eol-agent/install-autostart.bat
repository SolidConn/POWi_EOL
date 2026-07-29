@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM Install (or remove) the EOL jig agent as a login auto-start on THIS PC.
REM   install-autostart.bat          → agent launches every time you log in
REM   install-autostart.bat remove   → stop auto-starting
REM Per-user, no admin rights, fully reversible (deletes one .lnk).
REM ─────────────────────────────────────────────────────────────────────────
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LNK=%STARTUP%\EOL Jig Agent.lnk"
set "TARGET=%~dp0start-agent.bat"

if /i "%~1"=="remove" (
  if exist "%LNK%" ( del "%LNK%" & echo Auto-start removed. ) else ( echo Auto-start was not installed. )
  pause & exit /b 0
)

powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%LNK%');" ^
  "$s.TargetPath='%TARGET%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.WindowStyle=1;" ^
  "$s.Description='EOL jig agent (ws://localhost:9151)';" ^
  "$s.Save()"

if exist "%LNK%" ( echo Auto-start installed. The agent will launch at every login. ) else ( echo FAILED to create the shortcut. )
pause
