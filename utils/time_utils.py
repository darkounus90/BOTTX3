from datetime import datetime
import pytz

def get_ny_time():
    """
    Retorna siempre la hora actual de Nueva York (EST/EDT) 
    independientemente de la zona horaria del VPS.
    """
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz)

def get_local_now():
    """Fallback si no es necesario obligatoriamente NY"""
    return datetime.now()
