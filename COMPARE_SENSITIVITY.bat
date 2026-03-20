@echo off
setlocal enabledelayedexpansion

:: 📊 TX3 PRO - COMPARATIVA DE SENSIBILIDAD (DEBUG MODE)
:: ====================================================

echo [*] Verificando entorno...

:: Detectar comando python
set PY_CMD=python
python --version >nul 2>&1
if errorlevel 1 (
    set PY_CMD=python3
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se detecto 'python' ni 'python3' en el sistema.
        pause
        exit /b
    )
)

echo [*] Usando comando: %PY_CMD%

:: CARGAR VARIABLES DE ENTORNO
if exist .env (
    for /f "tokens=*" %%i in (.env) do set %%i
)

echo.
echo [1/3] PROBANDO: MODO RIGIDO (ESTANDAR ACTUAL)
echo ---------------------------------------------
%PY_CMD% scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
if exist data\backtest_results.json (
    move data\backtest_results.json data\results_RIGIDO.json >nul
)

echo.
echo [2/3] PROBANDO: MODO EQUILIBRADO (RECOMENDADO)
echo ---------------------------------------------
%PY_CMD% -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.5', 'self.z_threshold = 2.2'); open('strategy/zscore_reversion.py', 'w').write(c)"
%PY_CMD% -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 35.0', 'self.adx_threshold = 30.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

%PY_CMD% scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
if exist data\backtest_results.json (
    move data\backtest_results.json data\results_EQUILIBRADO.json >nul
)

echo.
echo [3/3] PROBANDO: MODO AGRESIVO (MAX FRECUENCIA)
echo ---------------------------------------------
%PY_CMD% -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.2', 'self.z_threshold = 2.0'); open('strategy/zscore_reversion.py', 'w').write(c)"
%PY_CMD% -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 30.0', 'self.adx_threshold = 25.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

%PY_CMD% scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
if exist data\backtest_results.json (
    move data\backtest_results.json data\results_AGRESIVO.json >nul
)

:: REVERTIR CAMBIOS
%PY_CMD% -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.0', 'self.z_threshold = 2.5'); open('strategy/zscore_reversion.py', 'w').write(c)"
%PY_CMD% -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 25.0', 'self.adx_threshold = 35.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

echo.
echo ============================================================
echo ✅ PROCESO COMPLETADO
echo Revisa la carpeta 'data/' para ver los 3 archivos JSON.
echo ============================================================
pause

