"""
🕐 Session Filter - Filtro de Sesiones de Trading
===================================================
Filtra las horas de trading para operar solo durante
sesiones de alta liquidez.
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from config.settings import SessionConfig
from utils.logger import BotLogger

# 🛡️ HELPER: Reloj Blindado pro-Windows (Fallback manual si falla ZoneInfo)
def get_now_institutional(tz_name: str):
    """Obtiene el 'ahora' de forma robusta, con fallback para Windows sin tzdata."""
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        now_utc = datetime.now(timezone.utc)
        if tz_name == "Europe/Prague":
            return now_utc + timedelta(hours=1)
        elif tz_name == "America/New_York":
            # NY esta en UTC-5 (Invierno) o UTC-4 (Verano)
            # Aproximamos a UTC-5 para compliance base
            return now_utc - timedelta(hours=5)
        return datetime.now()


class SessionFilter:
    """
    Filtra las sesiones de trading.

    Solo opera durante:
    - London Session:  3:00 AM - 12:00 PM EST
    - New York Session: 8:00 AM - 5:00 PM EST
    - Tokyo Session:    7:00 PM - 2:00 AM EST (Asian Open)
    - Overlap (mejor):  8:00 AM - 12:00 PM EST

    No opera los fines de semana (sábado y domingo).
    """

    # Tipos de sesión
    OVERLAP = "OVERLAP"      # Mejor momento para tradear
    ACTIVE = "ACTIVE"        # Sesión activa (London o NY)
    CLOSED = "CLOSED"        # Fuera de horario

    def __init__(self, logger: BotLogger):
        self.logger = logger

        # Definir horarios
        self.london_start = time(
            SessionConfig.LONDON_START_HOUR,
            SessionConfig.LONDON_START_MINUTE,
        )
        self.london_end = time(
            SessionConfig.LONDON_END_HOUR,
            SessionConfig.LONDON_END_MINUTE,
        )
        self.ny_start = time(
            SessionConfig.NY_START_HOUR,
            SessionConfig.NY_START_MINUTE,
        )
        self.ny_end = time(
            SessionConfig.NY_END_HOUR,
            SessionConfig.NY_END_MINUTE,
        )
        self.tokyo_start = time(
            SessionConfig.TOKYO_START_HOUR,
            SessionConfig.TOKYO_START_MINUTE,
        )
        self.tokyo_end = time(
            SessionConfig.TOKYO_END_HOUR,
            SessionConfig.TOKYO_END_MINUTE,
        )
        self.sydney_start = time(
            SessionConfig.SYDNEY_START_HOUR,
            SessionConfig.SYDNEY_START_MINUTE,
        )
        self.sydney_end = time(
            SessionConfig.SYDNEY_END_HOUR,
            SessionConfig.SYDNEY_END_MINUTE,
        )
        self.overlap_start = time(
            SessionConfig.OVERLAP_START_HOUR,
            SessionConfig.OVERLAP_START_MINUTE,
        )
        self.overlap_end = time(
            SessionConfig.OVERLAP_END_HOUR,
            SessionConfig.OVERLAP_END_MINUTE,
        )

        self.trading_days = SessionConfig.TRADING_DAYS

    def get_current_session(self) -> str:
        """
        Determina la sesión de trading actual.

        Returns:
            'OVERLAP' - Mejor momento (London + NY)
            'ACTIVE'  - Sesión London o NY activa
            'CLOSED'  - Fuera de horario
        """
        from config.settings import BotConfig
        now = get_now_institutional(BotConfig.MARKET_TIMEZONE)
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Verificar día de la semana (solo Lunes a Viernes)
        if current_day not in self.trading_days:
            return self.CLOSED

        # Verificar overlap (el mejor momento)
        if self.overlap_start <= current_time <= self.overlap_end:
            return self.OVERLAP

        # Verificar sesiones individuales
        in_london = self.london_start <= current_time <= self.london_end
        in_ny = self.ny_start <= current_time <= self.ny_end
        in_tokyo = current_time >= self.tokyo_start or current_time <= self.tokyo_end
        in_sydney = current_time >= self.sydney_start or current_time <= self.sydney_end

        if getattr(SessionConfig, "RESTRICT_TO_LONDON_NY", True):
            in_tokyo = False
            in_sydney = False

        # Apagar si es viernes por la tarde (Evita spreads altos de fin de semana)
        if current_day == 4 and now.hour >= getattr(SessionConfig, "FRIDAY_FLAT_HOUR", 12):
            return self.CLOSED

        if in_london or in_ny or in_tokyo or in_sydney:
            return self.ACTIVE

        return self.CLOSED

    def get_operative_phase_info(self) -> dict:
        """
        Determina la fase estratégica específica basada en el arsenal del bot.
        """
        from config.settings import BotConfig
        now = get_now_institutional(BotConfig.MARKET_TIMEZONE)
        h = now.hour
        
        if 2 <= h < 3:
            return {
                "id": "PRE_LONDON",
                "name": "🕵️ PRE-LONDON (Liquidity Sweeps)",
                "active_strats": ["ILS Sweep"]
            }
        elif 3 <= h < 13:
            return {
                "id": "PRIME",
                "name": "🌪️ PRIME MOMENTUM (Londres + Mañana NY)",
                "active_strats": ["TTM Squeeze", "ILS Sweep"]
            }
        elif 13 <= h < 17:
            return {
                "id": "REVERSION",
                "name": "🔬 AFTERNOON REVERSION (Tarde NY)",
                "active_strats": ["Z-Score (GBP)", "ILS Sweep"]
            }
        else:
            return {
                "id": "HIBERNATION",
                "name": "💤 HIBERNACIÓN (Mercado Cerrado / Rollover)",
                "active_strats": []
            }

    def is_trading_allowed(self) -> bool:
        """
        Verifica si se permite tradear y loguea la fase operativa.
        """
        session = self.get_current_session()
        phase = self.get_operative_phase_info()
        
        # Solo loguear si la sesión o la fase cambió
        if not hasattr(self, '_last_notified_phase'):
            self._last_notified_phase = None

        if phase["id"] != self._last_notified_phase:
            if session == self.CLOSED or phase["id"] == "HIBERNATION":
                self.logger.info(f"🕐 {phase['name']} — No se buscan nuevas entradas")
            else:
                strats = ", ".join(phase["active_strats"])
                self.logger.success(f"🚀 FASE: {phase['name']} | Estrategias: [{strats}]")
            self._last_notified_phase = phase["id"]

        return session != self.CLOSED and phase["id"] != "HIBERNATION"

    def get_session_info(self) -> dict:
        """
        Retorna información detallada de la sesión actual.
        """
        from config.settings import BotConfig
        now = get_now_institutional(BotConfig.MARKET_TIMEZONE)
        current_time = now.time()
        current_day = now.weekday()

        is_weekday = current_day in self.trading_days
        in_london = self.london_start <= current_time <= self.london_end
        in_ny = self.ny_start <= current_time <= self.ny_end
        in_tokyo = current_time >= self.tokyo_start or current_time <= self.tokyo_end
        in_sydney = current_time >= self.sydney_start or current_time <= self.sydney_end
        in_overlap = self.overlap_start <= current_time <= self.overlap_end

        session = self.get_current_session()

        return {
            "session": session,
            "time": current_time.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
            "is_weekday": is_weekday,
            "in_london": in_london,
            "in_ny": in_ny,
            "in_tokyo": in_tokyo,
            "in_sydney": in_sydney,
            "in_overlap": in_overlap,
            "trading_allowed": session != self.CLOSED,
        }

    def time_until_next_session(self) -> str:
        """Calcula el tiempo hasta la próxima sesión de trading"""
        now = datetime.now()
        current_time = now.time()

        if self.get_current_session() != self.CLOSED:
            return "Sesión activa"

        # Si es fin de semana, calcular hasta el lunes
        if now.weekday() == 5:  # Sábado
            hours_to_monday = 48 - now.hour + self.london_start.hour
            return f"~{hours_to_monday}h (hasta lunes)"
        elif now.weekday() == 6:  # Domingo
            hours_to_monday = 24 - now.hour + self.london_start.hour
            return f"~{hours_to_monday}h (hasta lunes)"

        # Si es día entre semana pero fuera de horario
        if current_time < self.london_start:
            diff_hours = self.london_start.hour - current_time.hour
            return f"~{diff_hours}h (hasta London open)"
        else:
            return "Mañana"

    def is_daily_reset_time(self) -> bool:
        """
        Verifica si es hora del reset diario de FTMO (00:00 Medianoche Praga).
        Retorna True si estamos en el primer minuto del día en Praga.
        """
        from config.settings import BotConfig
        from zoneinfo import ZoneInfo
        now_prague = datetime.now(ZoneInfo(BotConfig.FTMO_TIMEZONE))
        
        return now_prague.hour == 0 and now_prague.minute == 0

    def is_friday_forced_close_time(self) -> bool:
        """
        Verifica si es viernes por la tarde para cerrar todas las posiciones
        y evitar operar durante el fin de semana (Regla de Prop Firms).
        Se ejecuta a la hora parametrizada en FRIDAY_FLAT_HOUR (Por defecto 12:00 PM EST).
        """
        from config.settings import BotConfig
        now = datetime.now(ZoneInfo(BotConfig.MARKET_TIMEZONE))
        # 4 = Viernes en Python datetime.weekday()
        if now.weekday() == 4:
            if now.hour >= getattr(SessionConfig, "FRIDAY_FLAT_HOUR", 12):
                return True
        return False
