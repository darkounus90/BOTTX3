@echo off
setlocal enabledelayedexpansion

:: 📊 TX3 PRO - COMPARATIVA DE SENSIBILIDAD CONSOLIDADA
:: ====================================================

echo [*] Verificando entorno...
set PY_CMD=python
python --version >nul 2>&1
if errorlevel 1 (
    set PY_CMD=python3
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] No se detecto 'python' ni 'python3'.
        pause
        exit /b
    )
)

echo [*] Ejecutando Backtest de Sensibilidad (Rigido vs Equilibrado vs Agresivo)...
echo [*] Este proceso puede tardar unos minutos...

%PY_CMD% scripts/strategy_backtester.py --days 30 --symbols EURUSD,GBPUSD --mode sensitivity

echo.
echo ============================================================
echo ✅ PROCESO COMPLETADO
echo.
echo El reporte consolidado se encuentra en:
echo 📂 data/backtest_results.json
echo ============================================================
pause


