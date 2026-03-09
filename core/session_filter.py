"""
🕐 Session Filter - Filtro de Sesiones de Trading
===================================================
Filtra las horas de trading para operar solo durante
sesiones de alta liquidez.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo
from config.settings import SessionConfig
from utils.logger import BotLogger


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
        now = datetime.now(ZoneInfo("America/New_York"))
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Verificar día de la semana
        # Domingo después de 5 PM EST = mercado abierto (sesión asiática)
        is_sunday_open = (current_day == 6 and now.hour >= 17)
        if current_day not in self.trading_days and not is_sunday_open:
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

    def is_trading_allowed(self) -> bool:
        """
        Verifica si se permite tradear en este momento.
        """
        session = self.get_current_session()
        
        # Solo loguear si la sesión cambió para evitar spam en el loop
        if not hasattr(self, '_last_notified_session'):
            self._last_notified_session = None

        if session != self._last_notified_session:
            if session == self.CLOSED:
                self.logger.info("🕐 Mercado cerrado — Fuera de horario de trading")
            elif session == self.OVERLAP:
                self.logger.info("🟢 Sesión OVERLAP activa (London + NY)")
            elif session == self.ACTIVE:
                self.logger.info("🟡 Sesión activa")
            self._last_notified_session = session

        return session != self.CLOSED

    def get_session_info(self) -> dict:
        """
        Retorna información detallada de la sesión actual.
        """
        now = datetime.now(ZoneInfo("America/New_York"))
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
        Verifica si es hora del reset diario (5 PM EST).
        Retorna True si estamos en el minuto del reset.
        """
        now = datetime.now()
        from config.settings import BotConfig
        return (
            now.hour == BotConfig.DAILY_RESET_HOUR_EST
            and now.minute == BotConfig.DAILY_RESET_MINUTE_EST
        )

    def is_friday_forced_close_time(self) -> bool:
        """
        Verifica si es viernes por la tarde para cerrar todas las posiciones
        y evitar operar durante el fin de semana (Regla de Prop Firms).
        Se ejecuta a la hora parametrizada en FRIDAY_FLAT_HOUR (Por defecto 12:00 PM EST).
        """
        now = datetime.now(ZoneInfo("America/New_York"))
        # 4 = Viernes en Python datetime.weekday()
        if now.weekday() == 4:
            if now.hour >= getattr(SessionConfig, "FRIDAY_FLAT_HOUR", 12):
                return True
        return False
