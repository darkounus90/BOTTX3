@echo off
cd /d "%~dp0"
title Diagnostico del Bot TX3 PRO
color 0B
echo.
echo Presiona enter para comenzar el diagnostico...
pause
echo =======================================================
echo          TX3 PRO BOT - DIAGNOSTICO DE SISTEMA
echo =======================================================
echo.
echo Ejecutando verificacion de todas las funciones del bot...
echo.

if exist ".venv\Scripts\python.exe" goto use_venv

echo Entorno virtual no encontrado, usando python global...
python bot_diagnostics.py
goto end_diagnostics

:use_venv
echo Usando entorno virtual local...
.venv\Scripts\python.exe bot_diagnostics.py

:end_diagnostics
echo.
echo =======================================================
echo Diagnostico finalizado. 
echo Si el archivo DIAGNOSTICO_REPORTE.txt se genero exitosamente,
echo puedes abrirlo para ver los detalles.
echo =======================================================
echo.
pause
