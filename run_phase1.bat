@echo off
echo ==========================================
echo TX3 Pro Bot - Script de Arranque (Fase 1)
echo ==========================================

:: 1. Configura tus credenciales de Telegram aquí:
set TELEGRAM_BOT_TOKEN=AQUI_TU_TOKEN_DE_BOT
set TELEGRAM_CHAT_ID=AQUI_TU_CHAT_ID

:: (Opcional) Contraseña para el dashboard web
set DASHBOARD_SECRET=tx3-pro-bot-secret

:: 2. Ejecutar el bot en Fase 1
echo 🚀 Iniciando TX3 Pro Bot - Fase 1...
python main.py --phase 1
pause
