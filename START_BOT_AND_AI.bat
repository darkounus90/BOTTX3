@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    🌌 TX3 PRO BOT - ARRANQUE INTELIGENTE AUTOMATIZADO
echo ==========================================================
echo.

:: --- 1. DETECCIÓN DE PYTHON Y VENV ---
echo [1/3] Detectando Entorno de Ejecucion Limpio...

:: Limpiar basuras de instalaciones y venvs pasadas
set PYTHONHOME=
set PYTHONPATH=

set PY_EXE=python
where %PY_EXE% >nul 2>nul
if errorlevel 1 (
    echo    ❌ ERROR CRITICO: Python NO esta instalado o no esta en el PATH.
    echo    Por favor sigue las instrucciones en Telegram para reinstalarlo.
    pause
    exit /b
)

echo    - Usando ejecutable: %PY_EXE%
%PY_EXE% -m pip install -r requirements.txt
if errorlevel 1 (
    echo    ⚠️ Advertencia: Fallo el PIP install, pero intentaremos arrancar...
)
echo.

:: --- 2. VERIFICACIÓN DE IA ---
echo [2/3] Verificando Memoria de Machine Learning...
if not exist "data\rf_model_EURUSD.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado por primera vez.
    %PY_EXE% scripts\train_ml_model.py
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
%PY_EXE% main.py --phase 1
if errorlevel 1 (
    echo.
    echo ❌ ERROR: El bot se detuvo inesperadamente.
)
pause
