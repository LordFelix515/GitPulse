@echo off
chcp 65001 > nul
title GitPulse
cd /d "%~dp0"
python gitpulse.py %*
pause
