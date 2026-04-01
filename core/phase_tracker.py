"""
🎯 Phase Tracker - Tracking de Progreso por Fase
==================================================
Monitorea el progreso hacia el objetivo de cada fase del challenge.
"""

import MetaTrader5 as mt5
from config.settings import ChallengeConfig
from utils.logger import BotLogger


class PhaseTracker:
    """
    Rastrea el progreso del challenge por fase.

    Fase 1: 10% profit target ($5,000) + 4 días rentables
    Fase 2: 5% profit target ($2,500) + 4 días rentables

    Un día rentable = ganancia >= $250 (0.5% de $50k)
    Regla de consistencia: máx 40% de ganancias en un solo día.
    """

    def __init__(self, logger: BotLogger, phase: int):
        self.logger = logger
        self.phase = phase

        # Configuración de la fase
        self.balance_inicial = ChallengeConfig.BALANCE_INICIAL
        self.profit_target = ChallengeConfig.get_profit_target(phase)
        self.profit_target_pct = ChallengeConfig.get_profit_target_pct(phase)
        self.min_trading_days = ChallengeConfig.MIN_TRADING_DAYS
        self.min_profit_per_day = ChallengeConfig.MIN_PROFIT_PER_DAY
        self.consistency_rule_pct = ChallengeConfig.CONSISTENCY_RULE_PCT

        # Tracking
        self.profitable_days = 0
        self.daily_profits: list[float] = []
        self.current_day_profit = 0.0
        self.total_trading_days = 0

        self.logger.phase(
            f"Phase Tracker inicializado | Fase {phase} | "
            f"Target: ${self.profit_target:,.0f} ({self.profit_target_pct}%)"
        )

    def recalculate_profitable_days_from_mt5(self):
        """
        Recalcula los días rentables directamente del historial real de MT5.
        Esto garantiza que el conteo sea correcto incluso si el bot se reinicia
        o el archivo de estado se pierde.
        """
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from collections import defaultdict

        from config.settings import BotConfig
        _TZ = ZoneInfo(BotConfig.TIMEZONE)

        try:
            # Obtener historial completo (últimos 60 días cubre cualquier challenge)
            now = datetime.now(_TZ)
            start = now - timedelta(days=60)
            deals = mt5.history_deals_get(start, now + timedelta(hours=1))

            if not deals:
                self.logger.warning("📅 Sin historial de MT5 para calcular días rentables")
                return

            # ─── DETECTAR OFFSET DEL BROKER DINÁMICAMENTE ───
            import time as time_module
            broker_offset = 0
            try:
                tick = mt5.symbol_info_tick("EURUSD")
                if tick:
                    broker_offset = tick.time - int(time_module.time())
            except: pass

            # Agrupar profit por día calendario (en ET corregido)
            daily_map = defaultdict(float)
            for deal in deals:
                if deal.entry not in [1, 2, 3]:  # Solo salidas (OUT)
                    continue
                
                # Convertir a UTC real y luego a nuestra TZ
                utc_timestamp = deal.time - broker_offset
                dt = datetime.fromtimestamp(utc_timestamp, tz=_TZ)
                day_key = dt.strftime("%Y-%m-%d")
                # Profit Neto = Beneficio Bruto + Comisión (que viene en negativo)
                net_profit = deal.profit + deal.commission
                daily_map[day_key] += net_profit

            # Contar días rentables (>= $250 mínimo)
            profitable = 0
            recalc_daily_profits = []
            for day_key in sorted(daily_map.keys()):
                day_profit = round(daily_map[day_key], 2)
                recalc_daily_profits.append(day_profit)
                if day_profit >= self.min_profit_per_day:
                    profitable += 1

            # Solo actualizar si el recálculo da un valor mayor (nunca reducir)
            if profitable > self.profitable_days:
                old = self.profitable_days
                self.profitable_days = profitable
                self.daily_profits = recalc_daily_profits
                self.total_trading_days = len(recalc_daily_profits)
                self.logger.success(
                    f"📅 Días rentables recalculados de MT5: {old} → {profitable} "
                    f"(de {len(daily_map)} días con operaciones)"
                )
            elif profitable == self.profitable_days and profitable > 0:
                self.logger.info(f"📅 Días rentables confirmados: {profitable}")
            else:
                self.logger.info(
                    f"📅 Recálculo MT5: {profitable} días rentables "
                    f"(estado guardado: {self.profitable_days})"
                )

        except Exception as e:
            self.logger.error(f"Error recalculando días rentables: {e}")

    def get_current_profit(self) -> float:
        """Obtiene el profit actual (incluye flotante) desde el balance inicial"""
        account_info = mt5.account_info()
        if account_info is None:
            return 0.0
        return account_info.equity - self.balance_inicial

    def update_daily_profit(self):
        """Actualiza el profit del día actual"""
        account_info = mt5.account_info()
        if account_info is None:
            return

        # El daily profit = ganancia de las operaciones cerradas en el día + flotante actual.
        from datetime import datetime
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)
        
        deals = mt5.history_deals_get(start_of_day, now)
        closed_profit = 0.0
        if deals:
             # entry 1=OUT, 2=INOUT, 3=OUT_BY (todos representan salidas con profit real)
             # Profit Neto = Profit Bruto + Comisión (que viene en negativo)
             closed_profit = sum((d.profit + d.commission) for d in deals if d.entry in [1, 2, 3])

        self.current_day_profit = closed_profit + account_info.profit

    def end_of_day(self):
        """
        Se llama al final del día de trading (5 PM EST).
        Evalúa si el día fue rentable y registra el resultado.
        """
        # Calcular profit del día
        # Nota: esto debería calcularse comparando balance actual vs inicio del día
        account_info = mt5.account_info()
        if account_info is None:
            return

        # Guardar el profit del día
        self.daily_profits.append(self.current_day_profit)
        self.total_trading_days += 1

        # ¿Fue un día rentable? (mínimo $250)
        if self.current_day_profit >= self.min_profit_per_day:
            self.profitable_days += 1
            self.logger.success(
                f"Día rentable #{self.profitable_days}: "
                f"+${self.current_day_profit:,.2f}"
            )
        elif self.current_day_profit > 0:
            self.logger.warning(
                f"Día positivo pero insuficiente: "
                f"+${self.current_day_profit:,.2f} "
                f"(mínimo: ${self.min_profit_per_day:,.2f})"
            )
        else:
            self.logger.warning(
                f"Día con pérdida: ${self.current_day_profit:,.2f}"
            )

        # Reset para el nuevo día
        self.current_day_profit = 0.0

    def check_consistency_rule(self) -> bool:
        """
        Verifica la regla de consistencia:
        Ningún día puede representar más del 40% de las ganancias totales.

        Returns:
            True si se cumple la regla
        """
        if len(self.daily_profits) == 0:
            return True

        total_profit = sum(p for p in self.daily_profits if p > 0)
        if total_profit <= 0:
            return True

        for i, day_profit in enumerate(self.daily_profits):
            if day_profit <= 0:
                continue

            day_pct = (day_profit / total_profit) * 100
            if day_pct > self.consistency_rule_pct:
                if total_profit > (self.profit_target * 0.01) and sum(1 for p in self.daily_profits if p > 0) > 1:
                    return False

        return True

    def get_max_single_day_profit(self) -> float:
        """
        Calcula el máximo profit permitido en un solo día
        para cumplir la regla de consistencia del 40%.

        Si ya tienes $3,000 de profit total, un día no debería
        haber ganado más de $1,200 (40% de $3,000).
        """
        current_profit = self.get_current_profit()
        if current_profit <= 0:
            # Si aún no hay ganancia, el primer día puede ganar todo
            return self.profit_target

        # El máximo es 40% de las ganancias totales proyectadas
        return current_profit * (self.consistency_rule_pct / 100)

    def check_phase_complete(self) -> dict:
        """
        Verifica si se completó la fase actual.

        Returns:
            dict con:
            - complete: True si se cumplieron todos los requisitos
            - profit_met: True si se alcanzó el profit target
            - days_met: True si se tienen suficientes días rentables
            - consistency_met: True si se cumple la regla de consistencia
            - current_profit: Profit actual
            - profitable_days: Días rentables
        """
        current_profit = self.get_current_profit()

        profit_met = current_profit >= self.profit_target
        days_met = self.profitable_days >= self.min_trading_days
        consistency_met = self.check_consistency_rule()

        complete = profit_met and days_met and consistency_met

        # Log del progreso
        import time
        current_time = time.time()
        if current_time - getattr(self, "_last_log_time", 0) > 3600:
            self.logger.log_phase_progress(
                phase=self.phase,
                current_profit=current_profit,
                target=self.profit_target,
                profitable_days=self.profitable_days,
                min_days=self.min_trading_days,
            )

            if consistency_met:
                self.logger.success("Regla de consistencia: ✅ OK")
            else:
                self.logger.warning("Regla de consistencia: ❌ VIOLADA")
            self._last_log_time = current_time

        if complete:
            self.logger.banner(f"🎉 ¡FASE {self.phase} COMPLETADA! 🎉")
            if self.phase == 1:
                self.logger.success("Ahora procede a la FASE 2")
            else:
                self.logger.success(
                    "¡CUENTA FONDEADA! Puedes solicitar payouts."
                )

        return {
            "complete": complete,
            "profit_met": profit_met,
            "days_met": days_met,
            "consistency_met": consistency_met,
            "current_profit": current_profit,
            "profit_target": self.profit_target,
            "profitable_days": self.profitable_days,
            "min_days": self.min_trading_days,
        }

    def get_status_summary(self) -> str:
        """Retorna un resumen del estado actual"""
        current_profit = self.get_current_profit()
        profit_pct = (current_profit / self.profit_target * 100) if self.profit_target > 0 else 0

        lines = [
            f"═══ FASE {self.phase} ═══",
            f"Profit:     ${current_profit:>8,.2f} / ${self.profit_target:>8,.2f} ({profit_pct:.1f}%)",
            f"Días rent.: {self.profitable_days}/{self.min_trading_days}",
            f"Días total: {self.total_trading_days}",
            f"Consist.:   {'✅' if self.check_consistency_rule() else '❌'}",
        ]
        return "\n".join(lines)
