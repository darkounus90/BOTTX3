@echo off
cd /d "%~dp0"
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
if exist "secrets.bat" (
    echo [i] Cargando credenciales seguras desde secrets.bat...
    call secrets.bat
) else (
    echo [WARNING] No se encontro secrets.bat. Se usaran variables de entorno del sistema.
)

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
