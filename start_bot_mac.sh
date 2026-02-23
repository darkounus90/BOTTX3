#!/bin/bash
clear
echo "=========================================================="
echo "   🌌 TX3 PRO BOT - ARRANQUE INTELIGENTE AUTOMATIZADO"
echo "=========================================================="
echo ""
echo "[1/3] Verificando e Instalando Librerias de Inteligencia Artificial..."
pip install -r requirements.txt
echo ""

echo "[2/3] Verificando Memoria de Machine Learning..."
if [ ! -f "data/rf_model_EURUSD.pkl" ]; then
    echo "   ⚠️ El Cerebro IA es nuevo y necesita ser entrenado por primera vez."
    echo "   🧠 Ejecutando el Scanner y Entrenador Espacial (Esto tardara 1-2 minutos)..."
    python3 scripts/train_ml_model.py
else
    echo "   ✅ El Cerebro IA ya esta cargado y en linea."
fi
echo ""

# 3. Configura tus credenciales de Telegram aquí si lo deseas (O usa entorno):
export TELEGRAM_BOT_TOKEN="8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg"
export TELEGRAM_CHAT_ID="1176201993"
export DASHBOARD_SECRET="tx3-pro-bot-secret"

echo "[3/3] 🚀 Arrancando Bot Principal en Fase 1..."
echo "=========================================================="
python3 main.py --phase 1
