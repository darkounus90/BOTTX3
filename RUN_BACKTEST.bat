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

:: Metodo infalible: Buscar la instalacion exacta de BOTTX3
if exist "venv312\Scripts\python.exe" (
    set "PY_EXE=venv312\Scripts\python.exe"
) else if exist "C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe" (
    set "PY_EXE=C:\Users\PC\AppData\Local\Programs\Python\Python310\python.exe"
) else if exist "C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PY_EXE=C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

if not defined PY_EXE (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_EXE set "PY_EXE=%%I"
        )
    )
)

if not defined PY_EXE (
    for /f "delims=" %%I in ('where py 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_EXE set "PY_EXE=%%I"
        )
    )
)

if not defined PY_EXE (
    echo.
    echo ❌ ERROR CRITICO: Python no fue encontrado de forma automatica.
    echo 💀 NO SE ENCONTRÓ PYTHON EN ABSOLUTO EN ESTA COMPUTADORA.
    pause
    exit /b
)

echo    - Usando ejecutable: "%PY_EXE%"
echo.
echo ═══════════════════════════════════════════════════════════════
echo   Esto puede tomar 30-60 segundos. Analizando miles de velas...
echo ═══════════════════════════════════════════════════════════════
echo.

echo [2/2] 🚀 Analizando Portafolio Forex Oficial de los ultimos 90 Dias (EURUSD)...
"%PY_EXE%" scripts\strategy_backtester.py --days 90 --symbols EURUSD

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║   ✅ BACKTEST COMPLETADO                                    ║
echo ║   Los resultados se guardaron en data\backtest_results.json  ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
