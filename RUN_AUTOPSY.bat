@echo off
title IA Forense: Autopsia de Trades TX3
color 0B
echo ==========================================================
echo 🧠 TX3 PRO BOT - AUTOPSIA DE INTELIGENCIA ARTIFICIAL (CIO)
echo ==========================================================
echo.
echo Iniciando escaneo forense de trades fallidos en el historial...
echo Por favor espera, el motor Quant (Z-Score) y el Oraculo (Gemini) estan conectandose a MT5.
echo.

python scripts\trade_autopsy.py

echo.
echo ==========================================================
echo [+] Analisis forense completado. Revisa las respuestas 
echo     arriba para ver por que el bot vetaria esas entradas.
echo ==========================================================
pause
