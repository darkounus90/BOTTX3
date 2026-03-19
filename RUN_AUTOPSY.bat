@echo off
title IA Forense: Autopsia de Trades TX3
color 0B
echo ==========================================================
echo 🧠 TX3 PRO BOT - AUTOPSIA DE INTELIGENCIA ARTIFICIAL (CIO)
echo ==========================================================
echo.
echo Iniciando escaneo forense de trades fallidos en el historial...
echo.

:: Configurar entorno para el Oracle
set TELEGRAM_BOT_TOKEN=8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg
set TELEGRAM_CHAT_ID=1176201993
set DASHBOARD_SECRET=tx3-pro-bot-secret
set HUGGINGFACE_TOKEN=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
set GEMINI_API_KEY=AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8,AIzaSyC1OgAyHJKbauD_-S9ohpGGpdsmLDFrO-4

python scripts\trade_autopsy.py

echo.
echo ==========================================================
echo [+] Analisis forense completado. Revisa las respuestas 
echo     arriba para ver por que el bot vetaria esas entradas.
echo ==========================================================
pause
