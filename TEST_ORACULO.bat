@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo     TX3 PRO BOT - TEST DE ORACULO IA (V2 PARCHEADO)
echo =======================================================
echo.

set "PY_EXE="
where python >nul 2>nul
if not errorlevel 1 set "PY_EXE=python"

if not defined PY_EXE (
    where py >nul 2>nul
    if not errorlevel 1 set "PY_EXE=py"
)

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
    for /d %%V in ("C:\Users\Administrator\AppData\Local\Programs\Python\Python*") do (
        if exist "%%V\python.exe" set "PY_EXE=%%V\python.exe"
    )
)

if not defined PY_EXE (
    echo [ERROR] No encuentro Python en este servidor.
    pause
    exit /b
)

echo [-] Python encontrado en: "!PY_EXE!"
echo [-] Lanzando prueba de IA...
echo.
"!PY_EXE!" scripts\test_oracle_integration.py

echo.
echo =======================================================
echo Test finalizado. Comprueba que el veredicto salio exitoso.
echo =======================================================
echo.
pause
