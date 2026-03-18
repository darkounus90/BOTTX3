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

REM Verificar que el entorno virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual .venv
    echo         Ejecuta: python -m venv .venv
    pause
    exit /b 1
)

echo [1/2] Activando entorno virtual...
call .venv\Scripts\activate.bat

echo [2/2] Ejecutando Backtester (60 dias de historia)...
echo.
echo ═══════════════════════════════════════════════════════════════
echo   Esto puede tomar 30-60 segundos. Analizando miles de velas...
echo ═══════════════════════════════════════════════════════════════
echo.

REM Ejecutar backtest para EURUSD (60 días)
python scripts\strategy_backtester.py --days 60 --symbol EURUSD

echo.
echo ───────────────────────────────────────────────────────────────
echo   Ahora analizando GBPUSD...
echo ───────────────────────────────────────────────────────────────
echo.

REM Ejecutar backtest para GBPUSD (60 días)
python scripts\strategy_backtester.py --days 60 --symbol GBPUSD

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   ✅ BACKTEST COMPLETADO                                    ║
echo ║   Los resultados se guardaron en data\backtest_results.json  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
