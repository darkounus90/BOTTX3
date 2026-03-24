@echo off
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

:: Ejecutar el script de integridad de Python
python scripts/check_integrity.py

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
