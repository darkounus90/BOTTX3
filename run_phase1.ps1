# ==========================================
# TX3 Pro Bot - Script de Arranque (Fase 1)
# ==========================================

# 1. Configura tus credenciales de Telegram aquí:
$env:TELEGRAM_BOT_TOKEN="8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg"
$env:TELEGRAM_CHAT_ID="1176201993"

# (Opcional) Contraseña para el dashboard web
$env:DASHBOARD_SECRET="tx3-pro-bot-secret"

# 2. Ejecutar el bot en Fase 1
Write-Host "🚀 Iniciando TX3 Pro Bot - Fase 1..." -ForegroundColor Cyan
python main.py --phase 1
Read-Host -Prompt "Presiona Enter para salir..."
