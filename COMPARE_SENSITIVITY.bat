@echo off
setlocal enabledelayedexpansion

:: 📊 TX3 PRO - COMPARATIVA DE SENSIBILIDAD (BACKTEST)
:: ================================================
:: Este script ejecuta 3 simulaciones seguidas con distintos niveles
:: de "dureza" para que veas cuántos trades se activan.

:: CARGAR VARIABLES DE ENTORNO (Si existen)
if exist .env (
    for /f "tokens=*" %%i in (.env) do set %%i
)

echo.
echo [1/3] PROBANDO: MODO RIGIDO (ESTANDAR ACTUAL)
echo ---------------------------------------------
echo Parametros: Z-Score = 2.5 | ADX Threshold = 35.0
:: Simulamos cambiando los parametros via flags si el script lo soporta, 
:: o simplemente informando que es la config base.
python scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
move data\backtest_results.json data\results_RIGIDO.json >nul

echo.
echo [2/3] PROBANDO: MODO EQUILIBRADO (RECOMENDADO)
echo ---------------------------------------------
echo Parametros: Z-Score = 2.2 | ADX Threshold = 30.0
:: Temp modification of strategies or script call
:: (Nota: El backtester actual usa los valores hardcoded en las clases de estrategia)
:: Creamos un flag temporal o modificamos el archivo para el test
python -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.5', 'self.z_threshold = 2.2'); open('strategy/zscore_reversion.py', 'w').write(c)"
python -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 35.0', 'self.adx_threshold = 30.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

python scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
move data\backtest_results.json data\results_EQUILIBRADO.json >nul

echo.
echo [3/3] PROBANDO: MODO AGRESIVO (MAX FRECUENCIA)
echo ---------------------------------------------
echo Parametros: Z-Score = 2.0 | ADX Threshold = 25.0
python -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.2', 'self.z_threshold = 2.0'); open('strategy/zscore_reversion.py', 'w').write(c)"
python -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 30.0', 'self.adx_threshold = 25.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

python scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD
move data\backtest_results.json data\results_AGRESIVO.json >nul

:: REVERTIR CAMBIOS A MODO RIGIDO ORIGINAL
python -c "import sys; c=open('strategy/zscore_reversion.py').read().replace('self.z_threshold = 2.0', 'self.z_threshold = 2.5'); open('strategy/zscore_reversion.py', 'w').write(c)"
python -c "import sys; c=open('strategy/bollinger_rsi.py').read().replace('self.adx_threshold = 25.0', 'self.adx_threshold = 35.0'); open('strategy/bollinger_rsi.py', 'w').write(c)"

echo.
echo ============================================================
echo ✅ PROCESO COMPLETADO
echo Los resultados estan en la carpeta 'data/':
echo 1. results_RIGIDO.json
echo 2. results_EQUILIBRADO.json
echo 3. results_AGRESIVO.json
echo ============================================================
pause
