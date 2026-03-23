@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    🌌 TX3 PRO BOT - ARRANQUE INTELIGENTE AUTOMATIZADO
echo ==========================================================
echo.

:: --- 1. DETECCIÓN DE PYTHON Y VENV ---
echo [1/3] Detectando Entorno de Ejecución...

set PY_EXE=python
where %PY_EXE% >nul 2>nul
if errorlevel 1 (
    set PY_EXE=python3
    where !PY_EXE! >nul 2>nul
    if errorlevel 1 (
        if exist ".venv\Scripts\python.exe" (
            set PY_EXE=".venv\Scripts\python.exe"
            echo    - Usando Entorno Virtual (.venv^) detectado.
        ) else if exist ".venv2\Scripts\python.exe" (
            set PY_EXE=".venv2\Scripts\python.exe"
            echo    - Usando Entorno Virtual (.venv2^) detectado.
        ) else (
            echo    ❌ ERROR: No se encontró 'python' ni '.venv'. 
            echo    Asegurate de tener Python instalado y en el PATH.
            pause
            exit /b
        )
    )
)

:: Verificar PIP a través del ejecutable de python detectado
echo    - Usando ejecutable: %PY_EXE%
%PY_EXE% -m pip install -r requirements.txt
if errorlevel 1 (
    echo    ⚠️ Advertencia: Falló el PIP install, pero intentaremos arrancar...
)
echo.

:: --- 2. VERIFICACIÓN DE IA ---
echo [2/3] Verificando Memoria de Machine Learning...
if not exist "data\rf_model_EURUSD.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado por primera vez.
    echo    - Ejecutando el Scanner y Entrenador Espacial - Esto tardará 1-2 minutos...
    %PY_EXE% scripts\train_ml_model.py
) else (
    echo    ✅ El Cerebro IA ya está cargado y en línea.
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
pause
