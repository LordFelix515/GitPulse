@echo off
chcp 65001 > nul
title GitPulse - Windows Başlangıcına Ekle
cd /d "%~dp0"
python gitpulse.py --add-startup
echo.
pause
