@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONUTF8=1
echo =======================================================
echo     TX3 PRO BOT - TEST DE ORACULO IA (V2 PARCHEADO)
echo =======================================================
echo.

set PYTHONHOME=
set PYTHONPATH=

set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.\.venv\Scripts\python.exe"
) else (
    :: 1. Búsqueda automática ultra-rápida (Ignora WindowsApps)
    for /d %%V in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
    if not defined PY_EXE (
        for /d %%U in ("C:\Users\*") do (
            for /d %%V in ("%%U\AppData\Local\Programs\Python\Python*") do (
                if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
            )
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

    :: 2. Fallback a PATH (filtrando la trampa de WindowsApps)
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
)

if not defined PY_EXE (
    echo [ERROR] No encuentro Python en este servidor.
    pause
    exit /b
)

echo [-] Python encontrado en: "!PY_EXE!"
echo [-] Asegurando librerias instaladas...
"!PY_EXE!" -m pip install MetaTrader5 google-generativeai --quiet

echo [-] Lanzando prueba de IA...
echo.
"!PY_EXE!" scripts\test_oracle_integration.py

echo.
echo =======================================================
echo Test finalizado. Comprueba que el veredicto salio exitoso.
echo =======================================================
echo.
pause
