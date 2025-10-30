@echo off
chcp 65001
cd /d "%~dp0"
python manage.py runserver
pause
