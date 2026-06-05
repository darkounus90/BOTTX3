import os
import sys
import psutil
import time
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.telegram_notifier import TelegramNotifier
from utils.logger import BotLogger

logger = BotLogger(name="HealthCheck")
telegram = TelegramNotifier(logger)

WARNING_THRESHOLD = 80.0

def get_system_health():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return cpu, ram, disk

def check_health():
    logger.info("Iniciando chequeo de salud del VPS...")
    cpu, ram, disk = get_system_health()
    
    logger.info(f"Métricas actuales -> CPU: {cpu}% | RAM: {ram}% | Disco: {disk}%")
    
    warnings = []
    if cpu > WARNING_THRESHOLD:
        warnings.append(f"⚠️ CPU al {cpu}%")
    if ram > WARNING_THRESHOLD:
        warnings.append(f"⚠️ RAM al {ram}%")
    if disk > WARNING_THRESHOLD:
        warnings.append(f"⚠️ Disco al {disk}%")
        
    if warnings:
        msg = "🚨 *ALERTA DE RECURSOS VPS* 🚨\n"
        msg += "El servidor está bajo alto estrés:\n\n"
        msg += "\n".join(warnings)
        msg += "\n\nRevise el Administrador de Tareas para evitar bloqueos del Bot FTMO."
        
        logger.warning("Umbrales superados. Enviando alerta a Telegram...")
        telegram._send(msg)
        logger.info("Alerta enviada.")
    else:
        logger.info("El servidor opera dentro de los límites normales.")

if __name__ == "__main__":
    check_health()
