@echo off
cd /d "%~dp0"
title Test de Integracion IA (Motor Real)
color 0A
echo.
echo =======================================================
echo     TX3 PRO BOT - TEST DE ORÁCULO IA (V2 PARCHEADO)
echo =======================================================
echo.

if exist ".venv\Scripts\python.exe" goto use_venv

echo Entorno virtual no encontrado, usando python global...
python scripts\test_oracle_integration.py
goto end_test

:use_venv
echo Usando entorno virtual local de Windows...
.\.venv\Scripts\python.exe scripts\test_oracle_integration.py

:end_test
echo.
echo =======================================================
echo Test finalizado. Comprueba que el veredicto salio exitoso.
echo =======================================================
echo.
pause
