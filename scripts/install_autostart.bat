@echo off
title Instalador de Auto-Arranque TX3 Pro (Anti-Windows Update)
color 0A

echo =======================================================
echo   VINCULANDO BOT TX3 A INCIO AUTOMATICO DE WINDOWS
echo =======================================================
echo.
echo Esto creara una tarea programada en tu servidor VPS para
echo que si Windows se reinicia, el Bot vuelva a encenderse 
echo automaticamente y siga gestionando las operaciones.
echo.

set "PYTHON_PATH=C:\Program Files\Cloudbase Solutions\Cloudbase-Init\Python\python.exe"
set "BOT_PATH=%cd%\main.py"
set "START_DIR=%cd%"

echo Detectado directorio actual: %START_DIR%

echo.
echo Creando Script Ejecutable de Lanzamiento...
echo @echo off > run_bot.bat
echo cd /d "%START_DIR%" >> run_bot.bat
echo "%PYTHON_PATH%" "%BOT_PATH%" >> run_bot.bat
echo echo El Bot se detuvo o crasheo. >> run_bot.bat
echo pause >> run_bot.bat

echo.
echo Creando tarea programada en Windows (Requiere Permisos de Administrador)...
schtasks /create /tn "BOTTX3_AutoStart" /tr "\"%START_DIR%\run_bot.bat\"" /sc onlogon /rl highest /f

echo.
echo =======================================================
echo ¡EXITO!
echo Si el VPS de FTMO se apaga y vuelve a prender, la tarea
echo BOTTX3_AutoStart ejecutara run_bot.bat automaticamente.
echo =======================================================
pause
