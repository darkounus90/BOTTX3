@echo off
cd /d "%~dp0"
set HUGGINGFACE_TOKEN=YOUR_HUGGINGFACE_TOKEN
echo ==========================================================
echo    TX3 PRO BOT - ARRANQUE INTELIGENTE
echo ==========================================================
echo.

echo [1/4] Abriendo MetaTrader 5 (Modo Inyeccion de Credenciales)...
echo.

echo [3/4] Verificando Memoria de Machine Learning (US100.cash)...
if not exist "data\rf_model_US100.cash.pkl" (
    echo    ! El Cerebro IA es nuevo y necesita ser entrenado.
    venv312\Scripts\python.exe scripts\train_ml_model.py
) else (
    echo    ✅ El Cerebro IA ya esta cargado y en linea.
)

echo [2/4] Detectando Entorno Python...
python --version
if not exist "venv312\Scripts\python.exe" (
    echo ⚙️ Entorno virtual no detectado. Creando e instalando requerimientos automaticamente...
    python -m venv venv312
    venv312\Scripts\pip.exe install -r requirements.txt
    echo ✅ Instalacion completada.
)
if errorlevel 1 (
    echo ❌ ERROR: Python no se encontro en el sistema.
    pause
    exit /b
)

:: --- 3. CREDENCIALES ---
set TELEGRAM_BOT_TOKEN=8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg
set TELEGRAM_CHAT_ID=1176201993
set DASHBOARD_SECRET=tx3-pro-bot-secret
set HUGGINGFACE_TOKEN=YOUR_HUGGINGFACE_TOKEN
set GEMINI_API_KEY=YOUR_GEMINI_API_KEY

:: --- CREDENCIALES FTMO (Rellena esto) ---
set MT5_LOGIN=1513537066
set MT5_PASSWORD=d2CNAhT@fQ53t
set MT5_SERVER=FTMO-Demo

echo [4/4] Arrancando Bot Principal (Fase 1 FTMO con Python 3.12)...
echo ==========================================================
:: Lanzar el Dashboard web en Modo App de forma automatica y paralela
start /b cmd /c "timeout /t 5 > nul && start msedge --app=http://localhost:5050 || start chrome --app=http://localhost:5050 || start http://localhost:5050"

venv312\Scripts\python.exe main.py --phase 1

if errorlevel 1 (
    echo.
    echo ❌ ERROR: El bot se detuvo inesperadamente.
)
pause
