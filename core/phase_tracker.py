"""
🎯 Phase Tracker - Tracking de Progreso por Fase (con Persistencia SQLite)
===========================================================================
CAMBIOS vs versión original:
  1. Importa StateStore.
  2. __init__: llama a _restore_from_db() al inicializar.
     Estrategia de restauración por capas:
       Capa 1 → DB (más reciente y confiable)
       Capa 2 → recalculate_profitable_days_from_mt5() si DB está vacía
     Así, aunque la DB se borre, el bot recupera el estado desde MT5.
  3. end_of_day(), update_daily_profit(): llaman a _persist() al terminar.
  4. recalculate_profitable_days_from_mt5(): ahora llama _persist() cuando
     actualiza el estado (no solo en RAM sino también en disco).
"""

import MetaTrader5 as mt5
from config.settings import ChallengeConfig
from utils.logger import BotLogger
from utils.state_store import StateStore          # ← NUEVO


class PhaseTracker:
    """
    Rastrea el progreso del challenge por fase.
    Con persistencia SQLite: el conteo de días rentables y profits
    sobrevive reinicios del proceso.
    """

    def __init__(self, logger: BotLogger, phase: int):
        self.logger = logger
        self.phase = phase
        self._store = StateStore()                # ← NUEVO

        # Configuración de la fase (sin cambios)
        self.balance_inicial = ChallengeConfig.BALANCE_INICIAL
        self.profit_target = ChallengeConfig.get_profit_target(phase)
        self.profit_target_pct = ChallengeConfig.get_profit_target_pct(phase)
        self.min_trading_days = ChallengeConfig.MIN_TRADING_DAYS
        self.min_profit_per_day = ChallengeConfig.MIN_PROFIT_PER_DAY
        self.consistency_rule_pct = ChallengeConfig.CONSISTENCY_RULE_PCT

        # Estado (valores por defecto antes de restaurar)
        self.profitable_days: int = 0
        self.daily_profits: list[float] = []
        self.current_day_profit: float = 0.0
        self.total_trading_days: int = 0

        # ── Restauración en capas ──────────────────────────────────────
        restored_from_db = self._restore_from_db()

        if not restored_from_db:
            # Capa 2: recalcular desde MT5 si la DB está vacía
            self.logger.info("📂 DB vacía para esta fase. Recalculando desde historial MT5...")
            self.recalculate_profitable_days_from_mt5()
            # Si MT5 tampoco tiene nada, quedamos en cero (correcto para primera vez)

        self.logger.phase(
            f"Phase Tracker LISTO | Fase {phase} | "
            f"Target: ${self.profit_target:,.0f} ({self.profit_target_pct}%) | "
            f"Días rentables: {self.profitable_days}/{self.min_trading_days} | "
            f"Origen: {'DB ✅' if restored_from_db else 'MT5 recalc'}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PERSISTENCIA
    # ──────────────────────────────────────────────────────────────────────────

    def _restore_from_db(self) -> bool:
        """
        Restaura el estado más reciente desde la DB para esta fase.
        load_phase() sin trading_day devuelve el registro más reciente,
        que contiene el acumulado total (profitable_days puede abarcar varios días).
        """
        try:
            data = self._store.load_phase(self.phase)
            if data is None:
                return False

            self.profitable_days    = data["profitable_days"]
            self.total_trading_days = data["total_trading_days"]
            self.daily_profits      = data["daily_profits"]
            self.current_day_profit = data["current_day_profit"]

            self.logger.info(
                f"✅ PhaseTracker restaurado desde DB ({data['trading_day']}) | "
                f"días_rent={self.profitable_days} | "
                f"total_días={self.total_trading_days} | "
                f"profit_hoy=${self.current_day_profit:.2f}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error restaurando PhaseTracker desde DB: {e}")
            return False

    def _persist(self):
        """Escribe el estado actual en la DB. Falla silenciosamente."""
        try:
            self._store.save_phase(
                phase=self.phase,
                profitable_days=self.profitable_days,
                total_trading_days=self.total_trading_days,
                daily_profits=self.daily_profits,
                current_day_profit=self.current_day_profit,
            )
        except Exception as e:
            self.logger.error(f"Error al persistir PhaseTracker: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS ORIGINALES (con _persist() añadido donde cambia el estado)
    # ──────────────────────────────────────────────────────────────────────────

    def recalculate_profitable_days_from_mt5(self):
        """
        Recalcula los días rentables desde MT5.
        Ahora también persiste el resultado en la DB.
        """
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from collections import defaultdict
        from config.settings import BotConfig
        import time as time_module

        _TZ = ZoneInfo(BotConfig.TIMEZONE)

        try:
            now = datetime.now(_TZ)
            start = now - timedelta(days=60)
            deals = mt5.history_deals_get(start, now + timedelta(hours=1))

            if not deals:
                self.logger.warning("📅 Sin historial de MT5 para calcular días rentables")
                return

            broker_offset = 0
            try:
                tick = mt5.symbol_info_tick("EURUSD")
                if tick:
                    broker_offset = tick.time - int(time_module.time())
            except:
                pass

            daily_map = defaultdict(float)
            for deal in deals:
                if deal.type not in [0, 1]:
                    continue
                if deal.entry not in [1, 2, 3]:
                    continue
                utc_timestamp = deal.time - broker_offset
                dt = datetime.fromtimestamp(utc_timestamp, tz=_TZ)
                day_key = dt.strftime("%Y-%m-%d")
                net_profit = deal.profit + deal.commission
                daily_map[day_key] += net_profit

            profitable = 0
            recalc_daily_profits = []
            for day_key in sorted(daily_map.keys()):
                day_profit = round(daily_map[day_key], 2)
                recalc_daily_profits.append(day_profit)
                if day_profit >= self.min_profit_per_day:
                    profitable += 1

            if profitable > self.profitable_days:
                old = self.profitable_days
                self.profitable_days = profitable
                self.daily_profits = recalc_daily_profits
                self.total_trading_days = len(recalc_daily_profits)
                self.logger.success(
                    f"📅 Días rentables recalculados de MT5: {old} → {profitable} "
                    f"(de {len(daily_map)} días con operaciones)"
                )
                self._persist()                   # ← Guardar recálculo en DB

            elif profitable == self.profitable_days and profitable > 0:
                self.logger.info(f"📅 Días rentables confirmados: {profitable}")
            else:
                self.logger.info(
                    f"📅 Recálculo MT5: {profitable} días rentables "
                    f"(estado en DB: {self.profitable_days})"
                )

        except Exception as e:
            self.logger.error(f"Error recalculando días rentables: {e}")

    def get_current_profit(self) -> float:
        account_info = mt5.account_info()
        if account_info is None:
            return 0.0
        return account_info.equity - self.balance_inicial

    def update_daily_profit(self):
        """Actualiza el profit del día actual y lo persiste."""
        account_info = mt5.account_info()
        if account_info is None:
            return

        from datetime import datetime
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day)
        deals = mt5.history_deals_get(start_of_day, now)
        closed_profit = 0.0
        if deals:
            closed_profit = sum(
                (d.profit + d.commission) for d in deals if d.entry in [1, 2, 3]
            )

        self.current_day_profit = closed_profit + account_info.profit
        self._persist()                           # ← Guardar profit intradiario

    def end_of_day(self):
        """Se llama al final del día de trading (5 PM EST). Persiste al terminar."""
        account_info = mt5.account_info()
        if account_info is None:
            return

        self.daily_profits.append(self.current_day_profit)
        self.total_trading_days += 1

        if self.current_day_profit >= self.min_profit_per_day:
            self.profitable_days += 1
            self.logger.success(
                f"Día rentable #{self.profitable_days}: +${self.current_day_profit:,.2f}"
            )
        elif self.current_day_profit > 0:
            self.logger.warning(
                f"Día positivo pero insuficiente: +${self.current_day_profit:,.2f} "
                f"(mínimo: ${self.min_profit_per_day:,.2f})"
            )
        else:
            self.logger.warning(f"Día con pérdida: ${self.current_day_profit:,.2f}")

        self.current_day_profit = 0.0
        self._persist()                           # ← Persistir cierre de día

    # ──────────────────────────────────────────────────────────────────────────
    # check_consistency_rule, get_max_single_day_profit, check_phase_complete,
    # get_status_summary — sin ningún cambio vs original.
    # ──────────────────────────────────────────────────────────────────────────

    def check_consistency_rule(self) -> bool:
        if len(self.daily_profits) == 0:
            return True
        total_profit = sum(p for p in self.daily_profits if p > 0)
        if total_profit <= 0:
            return True
        for day_profit in self.daily_profits:
            if day_profit <= 0:
                continue
            day_pct = (day_profit / total_profit) * 100
            if day_pct > self.consistency_rule_pct:
                if total_profit > (self.profit_target * 0.01) and sum(1 for p in self.daily_profits if p > 0) > 1:
                    return False
        return True

    def get_max_single_day_profit(self) -> float:
        current_profit = self.get_current_profit()
        if current_profit <= 0:
            return self.profit_target
        return current_profit * (self.consistency_rule_pct / 100)

    def check_phase_complete(self) -> dict:
        current_profit = self.get_current_profit()
        profit_met = current_profit >= self.profit_target
        days_met = self.profitable_days >= self.min_trading_days
        consistency_met = self.check_consistency_rule()
        complete = profit_met and days_met and consistency_met

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
            self.logger.success("Regla de consistencia: ✅ OK") if consistency_met else self.logger.warning("Regla de consistencia: ❌ VIOLADA")
            self._last_log_time = current_time

        if complete:
            self.logger.banner(f"🎉 ¡FASE {self.phase} COMPLETADA! 🎉")
            if self.phase == 1:
                self.logger.success("Ahora procede a la FASE 2")
            else:
                self.logger.success("¡CUENTA FONDEADA! Puedes solicitar payouts.")

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
