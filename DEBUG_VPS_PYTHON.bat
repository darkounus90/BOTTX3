@echo off
setlocal

echo ==========================================================
echo    🔍 DIAGNOSTICO PROFUNDO DE ENTORNO VPS
echo ==========================================================
echo.

set PY_PATH=C:\Users\Administrator\venv\Scripts\python.exe

echo [1] Verificando existencia de Python en:
echo "%PY_PATH%"
if exist "%PY_PATH%" (
    echo ✅ El archivo EXISTE.
    echo.
    echo [2] Intentando ejecutar version...
    "%PY_PATH%" --version
    if errorlevel 1 (
        echo ❌ ERROR: El archivo existe pero NO se puede ejecutar (posible launcher roto).
    )
) else (
    echo ❌ ERROR: El archivo NO EXISTE en esa ruta.
)

echo.
echo [3] Variables de Entorno Criticas:
echo PATH: %PATH%
echo.
echo PYTHONHOME: %PYTHONHOME%
echo PYTHONPATH: %PYTHONPATH%
echo.

echo [4] Verificando integridad de PIP:
"%PY_PATH%" -m pip --version

echo.
echo ==========================================================
pause
