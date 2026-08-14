@echo off
REM ─────────────────────────────────────────────────────────────────────────
REM Build a distributable eol-agent release zip: a self-contained agent.exe
REM (PyInstaller onefile — no Python install needed on the jig PC) plus the
REM launcher scripts and setup notes. Run this whenever eol-agent code changes
REM and you want to publish a new station release from the /eol admin page.
REM   build-release.bat
REM Output: eol-agent\release\eol-agent-vX.Y.zip — upload that file.
REM ─────────────────────────────────────────────────────────────────────────
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 ( echo ERROR: 'python' is not on PATH. & pause & exit /b 1 )

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo PyInstaller not installed — installing it now...
  python -m pip install pyinstaller
  if errorlevel 1 ( echo FAILED to install PyInstaller. & pause & exit /b 1 )
)

REM Pull VERSION = "X.Y" straight out of agent.py — the single source of truth.
set VERSION=
for /f "tokens=2 delims==#" %%v in ('findstr /b "VERSION" agent.py') do (
  if not defined VERSION set VERSION=%%v
)
set VERSION=%VERSION: =%
set VERSION=%VERSION:"=%
if not defined VERSION ( echo ERROR: couldn't read VERSION from agent.py & pause & exit /b 1 )

echo Building eol-agent v%VERSION% ...
python -m PyInstaller --onefile --name agent --clean agent.py
if errorlevel 1 ( echo PyInstaller build FAILED. & pause & exit /b 1 )

set "OUTDIR=release\eol-agent-v%VERSION%"
if exist "%OUTDIR%" rmdir /s /q "%OUTDIR%"
mkdir "%OUTDIR%"
copy /y dist\agent.exe "%OUTDIR%\" >nul
copy /y start-agent.bat "%OUTDIR%\" >nul
copy /y register-protocol.bat "%OUTDIR%\" >nul
copy /y install-autostart.bat "%OUTDIR%\" >nul

> "%OUTDIR%\SETUP.txt" (
  echo EOL Jig Agent v%VERSION%
  echo ========================
  echo.
  echo 1. Unzip this folder anywhere on the jig PC ^(e.g. C:\eol-agent^).
  echo 2. Run register-protocol.bat ONCE. This registers the powi-eol:// link so
  echo    the "Start agent" button on the /eol admin page can launch the agent.
  echo    Per-user, no admin rights needed. Reversible: register-protocol.bat remove
  echo 3. Optional: run install-autostart.bat to have the agent launch every time
  echo    you log in to this PC. Reversible: install-autostart.bat remove
  echo 4. Otherwise, just double-click start-agent.bat whenever you need it running.
  echo    Closing that window stops the agent; it auto-restarts itself if it crashes.
  echo.
  echo No Python install needed on this PC - agent.exe is self-contained.
  echo J-Link / PCAN drivers and nrfutil still need to be installed separately,
  echo same as before - this package only replaces the Python/pip setup step.
  echo.
  echo Verify it's working: open the /eol page - a green "Jig agent connected"
  echo line means you're good to go.
)

set "ZIPNAME=release\eol-agent-v%VERSION%.zip"
if exist "%ZIPNAME%" del "%ZIPNAME%"
powershell -NoProfile -Command "Compress-Archive -Path '%OUTDIR%\*' -DestinationPath '%ZIPNAME%'"
if errorlevel 1 ( echo FAILED to zip the release. & pause & exit /b 1 )

echo.
echo Done: %CD%\%ZIPNAME%
echo Upload this file on the /eol page ^(admin panel ^> Jig agent releases^), then Publish it.
pause
