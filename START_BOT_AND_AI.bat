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
    :: Rescate de emergencia por si el PATH no se ha actualizado (terminal vieja)
    if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" (
        set PY_EXE="C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
    ) else if exist "C:\Program Files\Python312\python.exe" (
        set PY_EXE="C:\Program Files\Python312\python.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set PY_EXE="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    ) else (
        echo    ❌ ERROR CRITICO: Python NO esta instalado o tu ventana esta obsoleta.
        echo    Por favor CIERRA TODAS las ventanas negras y abre una nueva.
        pause
        exit /b
    )
)

echo    - Usando ejecutable: !PY_EXE!
!PY_EXE! -m pip install -r requirements.txt
if errorlevel 1 (
    echo    ⚠️ Advertencia: Fallo el PIP install, pero intentaremos arrancar...
)
echo.

:: --- 2. VERIFICACIÓN DE IA ---
echo [2/3] Verificando Memoria de Machine Learning...
if not exist "data\rf_model_EURUSD.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado por primera vez.
    !PY_EXE! scripts\train_ml_model.py
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
!PY_EXE! main.py --phase 1
if errorlevel 1 (
    echo.
    echo ❌ ERROR: El bot se detuvo inesperadamente.
)
pause
