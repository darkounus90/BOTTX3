@echo off
setlocal enabledelayedexpansion
title TX3 PRO - Reparador de Emergencia (Python/Venv)
color 0E

echo =======================================================
echo    🔧 REPARADOR DE EMERGENCIA - TX3 PRO BOT
echo =======================================================
echo.

:: 1. Matar procesos zombies
echo [-] Limpiando procesos de Python en memoria...
taskkill /f /im python.exe /t >nul 2>nul
taskkill /f /im py.exe /t >nul 2>nul

:: 2. Borrar venv corrupto si existe
if exist ".venv" (
    echo [-] Detectado entorno .venv corrupto. Borrando...
    rd /s /q ".venv"
    if errorlevel 1 (
        echo [!] Error borrando .venv. Asegurate de cerrar MetaTrader y carpetas abiertas.
        pause
        exit /b
    )
    echo [OK] Entorno borrado.
)

:: 3. Detectar el mejor Python disponible
echo [-] Buscando instalacion de Python estable...
set "PY_CMD="

:: Intentar con el Launcher 'py' (suele ser el mas fiable en Windows)
py --version >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3.12"
    !PY_CMD! --version >nul 2>nul
    if errorlevel 1 set "PY_CMD=py"
)

:: Fallback a python directo
if not defined PY_CMD (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo [CRITICO] No se encontro Python en el sistema.
    echo Por favor, instala Python 3.12 desde python.org y marca "Add to PATH".
    pause
    exit /b
)

echo [-] Usando: !PY_CMD!
echo.

:: 4. Crear nuevo entorno virtual LIMPIO
echo [-] Creando nuevo entorno virtual (esto puede tardar 1 minuto)...
!PY_CMD! -m venv .venv
if errorlevel 1 (
    echo [FALLO] No se pudo crear el venv. Intenta reinstalar Python manualmente.
    pause
    exit /b
)

:: 5. Instalar dependencias esenciales
echo [-] Instalando dependencias en el entorno protegido...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo [!] Hubo errores durante la instalacion. Intentando instalacion forzada de IA...
    .\.venv\Scripts\python.exe -m pip install google-generativeai MetaTrader5 pandas numpy Flask flask-session
)

echo.
echo =======================================================
echo    ✅ REPARACION FINALIZADA
echo =======================================================
echo.
echo 1. Ahora intenta correr TEST_ORACULO.bat para ver la IA.
echo 2. Si el test pasa, ya puedes usar START_BOT_AND_AI.bat.
echo.
pause
