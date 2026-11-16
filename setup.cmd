@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-panel.ps1"
if errorlevel 1 goto failed
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" -InstallOnly
if errorlevel 1 goto failed
echo.
echo O'rnatish tugadi. Premiere'ni qayta oching: Window ^> Extensions ^> Smart Voice Editor.
pause
goto end
:failed
echo O'rnatishda xato. Yuqoridagi xabarni tekshiring.
pause
:end
