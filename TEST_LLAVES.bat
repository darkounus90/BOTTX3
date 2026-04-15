@echo off
cd /d "%~dp0"
title Test de Llaves IA Gemini
color 0E
echo.
echo =======================================================
echo          TX3 PRO BOT - TEST DE LLAVES API
echo =======================================================
echo.

if exist ".venv\Scripts\python.exe" goto use_venv

echo Entorno virtual no encontrado, usando python global...
python scripts\test_keys_gemini.py
goto end_test

:use_venv
echo Usando entorno virtual local de Windows...
.\.venv\Scripts\python.exe scripts\test_keys_gemini.py

:end_test
echo.
echo =======================================================
echo Test finalizado. Lee los resultados arriba.
echo =======================================================
echo.
pause
