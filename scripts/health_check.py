import os
import sys
import time
import psutil
import logging
from datetime import datetime
import json
import urllib.request
import urllib.error

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL GUARDIÁN DEL VPS
# ═══════════════════════════════════════════════════════════════

# Umbrales críticos (Porcentaje 0-100)
CPU_CRITICAL_THRESHOLD = 85.0
RAM_CRITICAL_THRESHOLD = 85.0
DISK_CRITICAL_THRESHOLD = 90.0

# Intervalo de revisión en segundos (ej: cada 60 segundos)
CHECK_INTERVAL_SEC = 60

# Webhook de Discord/Telegram (Pon aquí tu URL para recibir alertas en tu móvil)
WEBHOOK_URL = "" 

# Configuración de Logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "vps_health.log")

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ═══════════════════════════════════════════════════════════════
# FUNCIONES
# ═══════════════════════════════════════════════════════════════

def send_webhook_alert(message: str):
    """Envía una alerta de emergencia al Webhook si está configurado"""
    if not WEBHOOK_URL:
        return
        
    try:
        # Detectar si es Discord o Slack (formato JSON básico)
        payload = json.dumps({"content": f"🚨 **VPS ALERTA CRÍTICA** 🚨\n{message}"}).encode('utf-8')
        req = urllib.request.Request(WEBHOOK_URL, data=payload, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logging.error(f"Error enviando Webhook: {e}")

def monitor_system():
    print("🛡️ Guardián del VPS Iniciado. Monitoreando Recursos (Presiona Ctrl+C para detener)...")
    logging.info("Servicio Health Check iniciado.")
    
    alert_cooldown = 0
    
    while True:
        try:
            # Obtener métricas reales
            cpu_usage = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            ram_usage = ram.percent
            disk_usage = psutil.disk_usage('/').percent
            
            alerts = []
            
            if cpu_usage >= CPU_CRITICAL_THRESHOLD:
                alerts.append(f"🔥 CPU Sobrecargada: {cpu_usage}% (Límite: {CPU_CRITICAL_THRESHOLD}%)")
                
            if ram_usage >= RAM_CRITICAL_THRESHOLD:
                alerts.append(f"💥 RAM Agotándose: {ram_usage}% (Límite: {RAM_CRITICAL_THRESHOLD}%)")
                
            if disk_usage >= DISK_CRITICAL_THRESHOLD:
                alerts.append(f"💾 Disco casi Lleno: {disk_usage}% (Límite: {DISK_CRITICAL_THRESHOLD}%)")
                
            # Si hay alguna alerta y ya pasó el cooldown
            if alerts:
                msg = " | ".join(alerts)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ ALERTA: {msg}")
                logging.warning(msg)
                
                if alert_cooldown <= 0:
                    send_webhook_alert(msg)
                    # Esperar 5 minutos antes de volver a enviar spam al webhook
                    alert_cooldown = 5 * 60 
            else:
                # Todo normal
                sys.stdout.write(f"\r[{datetime.now().strftime('%H:%M:%S')}] ✅ Estado OK | CPU: {cpu_usage:05.1f}% | RAM: {ram_usage:05.1f}% | Disco: {disk_usage:05.1f}%    ")
                sys.stdout.flush()
                
            if alert_cooldown > 0:
                alert_cooldown -= CHECK_INTERVAL_SEC
                
            time.sleep(CHECK_INTERVAL_SEC - 1) # Descontamos 1 seg del psutil
            
        except KeyboardInterrupt:
            print("\n🛑 Guardián detenido por el usuario.")
            logging.info("Servicio Health Check detenido.")
            break
        except Exception as e:
            logging.error(f"Error inesperado en loop: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitor_system()
