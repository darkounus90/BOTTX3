@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    🌌 TX3 PRO BOT - ARRANQUE INTELIGENTE AUTOMATIZADO
echo ==========================================================
echo.

:: Limpiar basuras de instalaciones y venvs pasadas
set PYTHONHOME=
set PYTHONPATH=

echo [1/3] Detectando Entorno de Ejecución Limpio...

set "PY_EXE="

:: 1. Intentar comandos nativos (PATH)
where python >nul 2>nul
if not errorlevel 1 set "PY_EXE=python"

if not defined PY_EXE (
    where py >nul 2>nul
    if not errorlevel 1 set "PY_EXE=py"
)

:: 2. Búsqueda automática ultra-rápida (Cualquier versión, 3.10 a 3.14+)
if not defined PY_EXE (
    for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files (x86)\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Users\Administrator\AppData\Local\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)

:: 3. Búsqueda de Fuerza Bruta Extrema
if not defined PY_EXE (
    echo.
    echo ❌ ERROR CRITICO: Python no fue encontrado de forma automatica en carpetas comunes.
    echo 🔍 Iniciando Búsqueda Extrema en todo el disco duro... (Tomará 1 a 2 minutos)
    for /f "delims=" %%I in ('dir /s /b "C:\python.exe" 2^>nul') do (
        set "PY_EXE=%%I"
        goto :found_fallback
    )
    :found_fallback
    if not defined PY_EXE (
        echo.
        echo 💀 NO SE ENCONTRÓ PYTHON EN ABSOLUTO EN ESTA COMPUTADORA.
        echo Tu sistema operativo VPS esta vacio. Instala Python desde la pagina oficial.
        pause
        exit /b
    )
)

echo    - Usando ejecutable: "%PY_EXE%"
"%PY_EXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo    ⚠️ Advertencia: Fallo el PIP install, pero intentaremos arrancar...
)
echo.

:: --- 2. VERIFICACIÓN DE IA ---
echo [2/3] Verificando Memoria de Machine Learning...
if not exist "data\rf_model_EURUSD.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado por primera vez.
    "%PY_EXE%" scripts\train_ml_model.py
) else (
    echo    ✅ El Cerebro IA ya esta cargado y en linea.
)
echo.

:: --- 3. CREDENCIALES ---
set TELEGRAM_BOT_TOKEN=8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg
set TELEGRAM_CHAT_ID=1176201993
set DASHBOARD_SECRET=tx3-pro-bot-secret
set HUGGINGFACE_TOKEN=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
set GEMINI_API_KEY=AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8,AIzaSyC1OgAyHJKbauD_-S9ohpGGpdsmLDFrO-4

echo [3/3] 🚀 Arrancando Bot Principal en Fase 1...
echo ==========================================================
"%PY_EXE%" main.py --phase 1
if errorlevel 1 (
    echo.
    echo ❌ ERROR: El bot se detuvo inesperadamente.
)
pause
