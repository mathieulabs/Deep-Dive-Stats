@echo off
cd /d "%~dp0.."
python dev_tools\build_release.py %*
pause
