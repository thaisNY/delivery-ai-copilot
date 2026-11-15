@echo off
cd /d "%~dp0"
if not exist .env (
  copy .env.example .env >nul
  echo Criei o arquivo .env. Abra ele e cole sua GEMINI_API_KEY, depois rode de novo.
  notepad .env
  pause
  exit /b
)
echo Subindo Postgres, API e front (a primeira vez demora alguns minutos)...
docker compose up -d --build
if errorlevel 1 (
  echo Deu erro. O Docker Desktop esta aberto?
  pause
  exit /b
)
echo Aguardando a API preparar os dados...
timeout /t 15 >nul
start http://localhost:5173
echo Pronto! Painel: http://localhost:5173   API: http://localhost:8000/docs
pause
