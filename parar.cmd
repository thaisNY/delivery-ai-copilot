@echo off
cd /d "%~dp0"
docker compose down
echo Parado. (Para apagar tambem o banco: docker compose down -v)
pause
