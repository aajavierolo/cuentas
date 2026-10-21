@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   ALTIUM FINANCIERO V19 - INICIO DOCKER
echo ==============================================

docker info >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Docker Desktop no esta iniciado o no responde.
    echo Inicia Docker Desktop y ejecuta nuevamente este archivo.
    pause
    exit /b 1
)

echo Construyendo e iniciando el contenedor...
docker compose up -d --build
if errorlevel 1 (
    echo.
    echo ERROR: No fue posible iniciar Altium Financiero.
    docker compose logs --tail=50
    pause
    exit /b 1
)

echo.
echo Altium Financiero esta disponible en:
echo http://localhost:8501
start "" "http://localhost:8501"
pause
