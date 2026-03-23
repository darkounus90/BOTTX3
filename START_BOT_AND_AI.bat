@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo    🌌 TX3 PRO BOT - ARRANQUE INTELIGENTE AUTOMATIZADO
echo ==========================================================
echo.

:: --- 1. CONFIGURACIÓN DEL EJECUTABLE DETECTADO EN EL VPS ---
echo [1/3] Configurando Python desde Venv Administrador...

:: Ruta oficial detectada en el VPS del usuario
set PY_EXE="C:\Users\Administrator\venv\Scripts\python.exe"

if not exist %PY_EXE% (
    echo    ❌ ERROR CRITICO: No se halló el ejecutable en la ruta:
    echo    ! %PY_EXE%
    echo    - Intentando búsqueda alternativa en el PATH...
    
    set PY_EXE=python
    where !PY_EXE! >nul 2>nul
    if errorlevel 1 (
        echo    ❌ FALLO TOTAL: Debe existir el entorno venv en Administrator para arrancar.
        pause
        exit /b
    )
)

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
