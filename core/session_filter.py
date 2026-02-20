"""
🕐 Session Filter - Filtro de Sesiones de Trading
===================================================
Filtra las horas de trading para operar solo durante
sesiones de alta liquidez.
"""

from datetime import datetime, time
from config.settings import SessionConfig
from utils.logger import BotLogger


class SessionFilter:
    """
    Filtra las sesiones de trading.

    Solo opera durante:
    - London Session:  3:00 AM - 12:00 PM EST
    - New York Session: 8:00 AM - 5:00 PM EST
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
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Verificar día de la semana
        if current_day not in self.trading_days:
            return self.CLOSED

        # Verificar overlap (el mejor momento)
        if self.overlap_start <= current_time <= self.overlap_end:
            return self.OVERLAP

        # Verificar sesiones individuales
        in_london = self.london_start <= current_time <= self.london_end
        in_ny = self.ny_start <= current_time <= self.ny_end

        if in_london or in_ny:
            return self.ACTIVE

        return self.CLOSED

    def is_trading_allowed(self) -> bool:
        """
        Verifica si se permite tradear en este momento.

        Returns:
            True si estamos en una sesión activa (OVERLAP o ACTIVE)
        """
        session = self.get_current_session()

        if session == self.CLOSED:
            self.logger.info("🕐 Mercado cerrado — Fuera de horario de trading")
            return False

        if session == self.OVERLAP:
            self.logger.info("🟢 Sesión OVERLAP activa (London + NY)")
        elif session == self.ACTIVE:
            self.logger.info("🟡 Sesión activa")

        return True

    def get_session_info(self) -> dict:
        """
        Retorna información detallada de la sesión actual.
        """
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()

        is_weekday = current_day in self.trading_days
        in_london = self.london_start <= current_time <= self.london_end
        in_ny = self.ny_start <= current_time <= self.ny_end
        in_overlap = self.overlap_start <= current_time <= self.overlap_end

        session = self.get_current_session()

        return {
            "session": session,
            "time": current_time.strftime("%H:%M:%S"),
            "day": now.strftime("%A"),
            "is_weekday": is_weekday,
            "in_london": in_london,
            "in_ny": in_ny,
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
        Se ejecuta a las 3:45 PM EST (15:45).
        """
        now = datetime.now()
        # 4 = Viernes en Python datetime.weekday()
        if now.weekday() == 4:
            # 15:45 PM EST = 3:45 PM
            if now.hour == 15 and now.minute >= 45:
                return True
        return False
