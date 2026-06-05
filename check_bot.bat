@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title 🛡️ TX3 Bot Institutional Auditor
color 0E
cls

echo ==========================================================
echo       TX3 PRO BOT - INSTITUTIONAL INTEGRITY AUDIT
echo ==========================================================
echo.
echo [*] Iniciando verificacion de modulos Core...
echo [*] Revisando Sincronía Prague (Reset) vs New York (Market)...
echo [*] Verificando Motor Anti-Correlacion Pearson...
echo.

:: 1. Búsqueda automática ultra-rápida (Ignora WindowsApps)
for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%V\python.exe" set "PY_CMD=%%V\python.exe"
)
if not defined PY_CMD (
    for /d %%U in ("C:\Users\*") do (
        for /d %%V in ("%%U\AppData\Local\Programs\Python\Python*") do (
            if exist "%%V\python.exe" set "PY_CMD=%%V\python.exe"
        )
    )
)
if not defined PY_CMD (
    for /d %%V in ("C:\Program Files\Python*") do (
        if exist "%%V\python.exe" set "PY_CMD=%%V\python.exe"
    )
)
if not defined PY_CMD (
    for /d %%V in ("C:\Program Files (x86)\Python*") do (
        if exist "%%V\python.exe" set "PY_CMD=%%V\python.exe"
    )
)

:: 2. Fallback a PATH (filtrando la trampa de WindowsApps)
if not defined PY_CMD (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_CMD set "PY_CMD=%%I"
        )
    )
)
if not defined PY_CMD (
    for /f "delims=" %%I in ('where py 2^>nul') do (
        set "tmp_py=%%I"
        if "!tmp_py:WindowsApps=!"=="!tmp_py!" (
            if not defined PY_CMD set "PY_CMD=%%I"
        )
    )
)

if not defined PY_CMD (
    echo.
    echo [X] ERROR: No se encontro Python instalado en este VPS.
    echo [!] Por favor instala Python 3.10+ desde python.org o la Microsoft Store.
    echo.
    pause
    exit /b 1
)

echo [*] Usando comando: %PY_CMD%
echo.

:: Ejecutar el script de integridad usando el comando detectado
%PY_CMD% scripts/check_integrity.py

:: Verificar el cogido de salida (Errorlevel)
if %errorlevel% neq 0 (
    echo.
    echo [X] ERROR CRITICO DETECTADO: El bot NO es seguro para operar.
    echo [!] Revisa las dependencias (MetaTrader5, numpy, google-generativeai)
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] AUDITORIA SUPREMA SUPERADA. El bot esta blindado.
echo.
echo ==========================================================
echo Sugerencia: Corre 'python main.py --phase 1 --dry-run' 
echo para una prueba visual en vivo en el Dashboard.
echo ==========================================================
echo.
pause
