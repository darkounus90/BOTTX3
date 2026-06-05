import os
import sys
import psutil
import time
import shutil
from datetime import datetime, timedelta
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

def rotate_logs():
    logger.info("Verificando rotación de logs...")
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    logs_dir = os.path.join(base_dir, 'logs')
    backup_dir = os.path.join(logs_dir, 'backup')
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        
    now = time.time()
    thirty_days_ago = now - (30 * 24 * 60 * 60)
    
    rotated_count = 0
    if os.path.exists(logs_dir):
        for filename in os.listdir(logs_dir):
            if filename.endswith(".log") or filename.endswith(".txt"):
                filepath = os.path.join(logs_dir, filename)
                if os.path.isfile(filepath):
                    file_mtime = os.path.getmtime(filepath)
                    if file_mtime < thirty_days_ago:
                        try:
                            shutil.move(filepath, os.path.join(backup_dir, filename))
                            rotated_count += 1
                        except Exception as e:
                            logger.error(f"No se pudo mover el log {filename}: {e}")
                            
    if rotated_count > 0:
        logger.info(f"Rotación completada: {rotated_count} archivos movidos a backup.")
    else:
        logger.info("No hay logs antiguos para rotar.")

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
    rotate_logs()
    check_health()
