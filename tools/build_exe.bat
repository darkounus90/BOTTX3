@echo off
echo ====================================================
echo TX3 Pro Bot - Creador de Ejecutable (.exe)
echo ====================================================
echo.
echo Asegurate de correr este archivo en tu entorno Windows,
echo donde tienes instalado MetaTrader5 y Python.
echo.
pause

echo.
echo [1/3] Instalando PyInstaller...
pip install pyinstaller

echo.
echo [2/3] Compilando el bot (esto puede tardar unos minutos)...
:: Se empaqueta main.py en un solo archivo (.exe)
:: Se incluye expresamente la carpeta dashboard/templates para la web
pyinstaller --noconfirm --onefile --console ^
    --name "TX3_Pro_Bot" ^
    --add-data "dashboard/templates;dashboard/templates" ^
    main.py

echo.
echo [3/3] Limpiando archivos temporales...
rmdir /S /Q build
del TX3_Pro_Bot.spec

echo.
echo ====================================================
echo COMPILACION EXITOSA!
echo ====================================================
echo.
echo Tu nuevo ejecutable se encuentra en la carpeta:
echo.
echo       --^>  dist\TX3_Pro_Bot.exe
echo.
echo Puedes mover ese archivo .exe a cualquier parte de tu PC.
echo Para correrlo, abre una consola (cmd/powershell) en donde 
echo guardes el .exe y escribe:
echo.
echo     TX3_Pro_Bot.exe --phase 1
echo.
pause
