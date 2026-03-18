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

REM Ejecutar backtest para EURUSD (60 días)
echo [1/2] Analizando EURUSD (60 dias)...
%PYTHON_CMD% scripts\strategy_backtester.py --days 60 --symbol EURUSD

echo.
echo ───────────────────────────────────────────────────────────────
echo [2/2] Analizando GBPUSD (60 dias)...
echo ───────────────────────────────────────────────────────────────
echo.

REM Ejecutar backtest para GBPUSD (60 días)
%PYTHON_CMD% scripts\strategy_backtester.py --days 60 --symbol GBPUSD

echo.
echo ───────────────────────────────────────────────────────────────
echo [3/3] Analizando AUDUSD (60 dias)...
echo ───────────────────────────────────────────────────────────────
echo.

REM Ejecutar backtest para AUDUSD (60 días)
%PYTHON_CMD% scripts\strategy_backtester.py --days 60 --symbol AUDUSD

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   ✅ BACKTEST COMPLETADO                                    ║
echo ║   Los resultados se guardaron en data\backtest_results.json  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
