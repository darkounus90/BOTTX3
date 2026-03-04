@echo off
echo ==========================================
echo TX3 Pro Bot - Script de Arranque (Fase 1)
echo ==========================================

:: 1. Configura tus credenciales de Telegram aquí:
set TELEGRAM_BOT_TOKEN=8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg
set TELEGRAM_CHAT_ID=1176201993

:: (Opcional) Contraseña para el dashboard web
set DASHBOARD_SECRET=tx3-pro-bot-secret
set GEMINI_API_KEY=AIzaSyAgAV3K-t5rv_P7ru_NpyI8rcgGWObWkS8,AIzaSyC1OgAyHJKbauD_-S9ohpGGpdsmLDFrO-4

:: 2. Ejecutar el bot en Fase 1
echo 🚀 Iniciando TX3 Pro Bot - Fase 1...
python main.py --phase 1
pause
