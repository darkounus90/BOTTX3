@echo off
echo ==========================================================
echo    🔍 BUSQUEDA DE PYTHON EN EL VPS (EMERGENCIA)
echo ==========================================================
echo.
echo Buscando python.exe en todo el disco C:...
echo (Esto puede tardar un poco, por favor espera)
echo.

dir /s /b C:\python.exe

echo.
echo ==========================================================
echo Si ves una ruta arriba, copiala para darsela al bot.
echo Si NO ves nada, Python NO esta instalado en este VPS.
echo ==========================================================
pause
