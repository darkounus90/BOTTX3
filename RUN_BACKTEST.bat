@echo off
chcp 65001 >nul
title TX3 PRO - BACKTESTER CUANTITATIVO DE ESTRATEGIAS

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO                 ║
echo ║   Analiza qué estrategias GANAN y cuáles PIERDEN dinero     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Detectar Python automáticamente
set PYTHON_CMD=python

REM Si existe .venv, usarlo. Si no, usar Python global.
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Usando entorno virtual .venv
    call .venv\Scripts\activate.bat
) else (
    echo [INFO] Usando Python global del sistema
)

echo.
echo ═══════════════════════════════════════════════════════════════
echo   Esto puede tomar 30-60 segundos. Analizando miles de velas...
echo ═══════════════════════════════════════════════════════════════
echo.

echo [🚀] Analizando Portfolio Oficial (EURUSD, GBPUSD)...
%PYTHON_CMD% scripts\strategy_backtester.py --days 60 --symbols EURUSD,GBPUSD

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   ✅ BACKTEST COMPLETADO                                    ║
echo ║   Los resultados se guardaron en data\backtest_results.json  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
