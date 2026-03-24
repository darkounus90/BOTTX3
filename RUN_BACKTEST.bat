@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title TX3 PRO - BACKTESTER CUANTITATIVO DE ESTRATEGIAS

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO                 ║
echo ║   Analiza qué estrategias GANAN y cuáles PIERDEN dinero     ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Limpiar basuras de instalaciones y venvs pasadas
set PYTHONHOME=
set PYTHONPATH=

echo [1/2] Detectando Entorno de Ejecución Limpio...

set "PY_EXE="

:: 1. Intentar comandos nativos (PATH)
where python >nul 2>nul
if not errorlevel 1 set "PY_EXE=python"

if not defined PY_EXE (
    where py >nul 2>nul
    if not errorlevel 1 set "PY_EXE=py"
)

:: 2. Búsqueda automática ultra-rápida (Cualquier versión, 3.10 a 3.14+)
if not defined PY_EXE (
    for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Program Files (x86)\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)
if not defined PY_EXE (
    for /d %%V in ("C:\Users\Administrator\AppData\Local\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)

:: 3. Búsqueda de Fuerza Bruta Extrema
if not defined PY_EXE (
    echo.
    echo ❌ ERROR CRITICO: Python no fue encontrado de forma automatica en carpetas comunes.
    echo 🔍 Iniciando Búsqueda Extrema en todo el disco duro... (Tomará 1 a 2 minutos)
    for /f "delims=" %%I in ('dir /s /b "C:\python.exe" 2^>nul') do (
        set "PY_EXE=%%I"
        goto :found_fallback
    )
    :found_fallback
    if not defined PY_EXE (
        echo.
        echo 💀 NO SE ENCONTRÓ PYTHON EN ABSOLUTO EN ESTA COMPUTADORA.
        echo Tu sistema operativo VPS esta vacio. Instala Python desde la pagina oficial.
        pause
        exit /b
    )
)

echo    - Usando ejecutable: "%PY_EXE%"
echo.
echo ═══════════════════════════════════════════════════════════════
echo   Esto puede tomar 30-60 segundos. Analizando miles de velas...
echo ═══════════════════════════════════════════════════════════════
echo.

echo [2/2] 🚀 Analizando Portfolio Oficial (EURUSD, GBPUSD)...
"%PY_EXE%" scripts\strategy_backtester.py --days 60 --symbols EURUSD,GBPUSD

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   ✅ BACKTEST COMPLETADO                                    ║
echo ║   Los resultados se guardaron en data\backtest_results.json  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
