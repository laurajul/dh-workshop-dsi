@echo off
echo.
echo ==============================================
echo   DH Workshop - Windows Setup
echo ==============================================
echo.
echo Downloading and running setup script...
echo (A terminal window will appear - do not close it)
echo.
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/laurajul/DH-Workshop/main/install_windows.ps1 | iex"
pause
