@echo off
setlocal
cd /d "%~dp0"

echo Deteniendo Altium Financiero V13...
docker compose down
if errorlevel 1 (
    echo ERROR: No fue posible detener el proyecto.
    pause
    exit /b 1
)

echo Proyecto detenido correctamente.
pause
