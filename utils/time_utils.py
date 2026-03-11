from config.settings import BotConfig
from zoneinfo import ZoneInfo

def get_bot_time():
    """
    Retorna la hora actual en la zona horaria del bot (Colombia).
    """
    return datetime.now(ZoneInfo(BotConfig.TIMEZONE))

def get_ny_time():
    """
    Retorna la hora actual de Nueva York (EST/EDT) 
    """
    return datetime.now(ZoneInfo("America/New_York"))

def get_local_now():
    """Fallback si no es necesario obligatoriamente NY"""
    return datetime.now()
