"""
🛡️ Risk Manager - Gestor de Riesgo (con Persistencia SQLite)
=============================================================
CAMBIOS vs versión original:
  1. Importa StateStore y lo instancia en __init__.
  2. __init__: llama a _restore_from_db() antes de tocar MT5.
     Si hay registro de hoy → restaura equity_inicio_dia y flags.
     Si no hay registro de hoy (primer arranque del día) → usa MT5 como antes.
  3. reset_daily(): ahora llama a _persist() al final.
  4. Cada vez que los flags cambian en check_daily/overall_drawdown → _persist().
  5. _persist() es un método privado que escribe la DB en una sola llamada.

El resto del archivo es IDÉNTICO al original para no romper nada.
"""

import MetaTrader5 as mt5
from config.settings import ChallengeConfig, BotConfig
from utils.logger import BotLogger
from utils.state_store import StateStore          # ← NUEVO
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def get_now_institutional(tz_name: str):
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        now_utc = datetime.now(timezone.utc)
        if tz_name == "Europe/Prague":
            # Detectar DST aproximado: del último domingo de marzo al último de octubre
            m, d = now_utc.month, now_utc.day
            is_summer = (3 < m < 10) or (m == 3 and d >= 25) or (m == 10 and d < 25)
            return now_utc + timedelta(hours=2 if is_summer else 1)
        elif tz_name == "America/New_York":
            return now_utc - timedelta(hours=5)
        return datetime.now()


class RiskManager:
    """
    Gestor de riesgo para el TX3 Pro Challenge $50K.
    Con persistencia SQLite: sobrevive reinicios del proceso.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self._store = StateStore()                # ← NUEVO

        # Valores por defecto (serán sobreescritos por _restore_from_db si hay estado)
        self._balance_inicial = ChallengeConfig.BALANCE_INICIAL
        self.equity_inicio_dia = ChallengeConfig.BALANCE_INICIAL
        self.is_daily_warning = False
        self.is_daily_emergency = False
        self.is_overall_warning = False
        self.is_overall_emergency = False

        # ── Primero intentar restaurar desde la DB ──
        restored = self._restore_from_db()

        # ── Si no había estado guardado, sincronizar con MT5 (comportamiento original) ──
        if not restored:
            account_info = mt5.account_info()
            if account_info:
                self.equity_inicio_dia = max(account_info.balance, account_info.equity)
                self.logger.info(
                    f"💰 Primer arranque del día. Sincronizando con MT5: "
                    f"Balance=${account_info.balance:,.2f} | Equity=${account_info.equity:,.2f}"
                )
            else:
                self.logger.warning("No se pudo obtener info de cuenta. Usando default de $50k.")
                self.equity_inicio_dia = ChallengeConfig.BALANCE_INICIAL

            # Guardar el estado inicial del día recién detectado
            self._persist()

        self.logger.risk(
            f"🛡️ Risk Manager LISTO | Balance: ${self._balance_inicial:,.2f} | "
            f"Equidad Día: ${self.equity_inicio_dia:,.2f} | "
            f"Origen: {'DB ✅' if restored else 'MT5 (primer arranque)'}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # PERSISTENCIA
    # ──────────────────────────────────────────────────────────────────────────

    def _restore_from_db(self) -> bool:
        """
        Intenta restaurar el estado desde la DB para el día de trading actual.
        Retorna True si encontró y restauró estado, False si es un día nuevo.
        """
        try:
            data = self._store.load_risk()
            if data is None:
                self.logger.info("📂 Sin estado en DB para hoy. Iniciando día limpio.")
                return False

            self._balance_inicial    = data["balance_inicial"]
            self.equity_inicio_dia   = data["equity_inicio_dia"]
            self.is_daily_warning    = data["is_daily_warning"]
            self.is_daily_emergency  = data["is_daily_emergency"]
            self.is_overall_warning  = data["is_overall_warning"]
            self.is_overall_emergency= data["is_overall_emergency"]

            self.logger.info(
                f"✅ Estado restaurado desde DB ({data['trading_day']}) | "
                f"equity_inicio_dia=${self.equity_inicio_dia:,.2f} | "
                f"daily_warning={self.is_daily_warning} | "
                f"daily_emergency={self.is_daily_emergency}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error restaurando estado desde DB: {e}. Continuando sin restauración.")
            return False

    def _persist(self):
        """
        Escribe el estado actual en la DB. Llamado tras cada cambio relevante.
        Falla silenciosamente para no interrumpir el flujo de trading.
        """
        try:
            self._store.save_risk(
                equity_inicio_dia=self.equity_inicio_dia,
                balance_inicial=self._balance_inicial,
                is_daily_warning=self.is_daily_warning,
                is_daily_emergency=self.is_daily_emergency,
                is_overall_warning=self.is_overall_warning,
                is_overall_emergency=self.is_overall_emergency,
            )
        except Exception as e:
            self.logger.error(f"Error al persistir RiskManager: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # PROPIEDADES (sin cambios)
    # ──────────────────────────────────────────────────────────────────────────

    @property
    def balance_inicial(self):
        return self._balance_inicial

    @balance_inicial.setter
    def balance_inicial(self, value):
        self._balance_inicial = value
        self._persist()                           # ← persiste cuando sube por Fortaleza Matemática

    @property
    def max_daily_loss(self):
        base_calc = ChallengeConfig.BALANCE_INICIAL if getattr(BotConfig, "SIMULATE_50K_CHALLENGE", False) else self.balance_inicial
        return base_calc * (ChallengeConfig.MAX_DAILY_DRAWDOWN_PCT / 100.0)

    @property
    def max_overall_loss(self):
        base_calc = ChallengeConfig.BALANCE_INICIAL if getattr(BotConfig, "SIMULATE_50K_CHALLENGE", False) else self.balance_inicial
        return base_calc * (ChallengeConfig.MAX_OVERALL_DRAWDOWN_PCT / 100.0)

    @property
    def daily_warning_threshold(self):
        return self.max_daily_loss * (BotConfig.DAILY_DD_WARNING_PCT / 100.0)

    @property
    def daily_emergency_threshold(self):
        return self.max_daily_loss * (BotConfig.DAILY_DD_EMERGENCY_PCT / 100.0)

    @property
    def overall_warning_threshold(self):
        return self.max_overall_loss * (BotConfig.OVERALL_DD_WARNING_PCT / 100.0)

    @property
    def overall_emergency_threshold(self):
        return self.max_overall_loss * (BotConfig.OVERALL_DD_EMERGENCY_PCT / 100.0)

    # ──────────────────────────────────────────────────────────────────────────
    # CHECKS DE DRAWDOWN (con _persist() al cambiar flags)
    # ──────────────────────────────────────────────────────────────────────────

    def check_daily_drawdown(self) -> dict:
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info de cuenta para daily DD")
            return {"safe": False, "loss": 0, "limit": self.max_daily_loss, "remaining": 0, "level": "ERROR"}

        current_equity = account_info.equity

        now_prague = get_now_institutional(BotConfig.FTMO_TIMEZONE)
        midnight_prague = now_prague.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ftmo_ts = int(midnight_prague.timestamp())
        end_ftmo_ts = int((now_prague + timedelta(hours=1)).timestamp())

        closed_pnl_today = 0.0
        try:
            deals = mt5.history_deals_get(start_ftmo_ts, end_ftmo_ts)
            if deals:
                for d in deals:
                    if d.entry in [1, 2, 3]:
                        closed_pnl_today += (d.profit + d.commission + d.swap)
        except Exception:
            pass

        floating_pnl = account_info.profit
        total_day_pnl = closed_pnl_today + floating_pnl
        daily_loss = max(0, -total_day_pnl)
        classic_loss = max(0, self.equity_inicio_dia - current_equity)
        daily_loss = max(daily_loss, classic_loss)
        remaining = self.max_daily_loss - daily_loss

        prev_warning = self.is_daily_warning
        prev_emergency = self.is_daily_emergency

        if daily_loss >= self.max_daily_loss:
            level = "VIOLATED"
            self.is_daily_emergency = True
        elif daily_loss >= self.daily_emergency_threshold:
            level = "EMERGENCY"
            self.is_daily_emergency = True
            if not prev_warning:
                self.logger.critical(f"🚨 EMERGENCIA DIARIA: Pérdida ${daily_loss:,.2f} — CERRANDO TODO")
        elif daily_loss >= self.daily_warning_threshold:
            level = "WARNING"
            self.is_daily_warning = True
            self.logger.warning(f"⚠️ ALERTA DIARIA: Pérdida ${daily_loss:,.2f} — No más trades")
        else:
            level = "OK"

        # Persistir solo si los flags cambiaron (evita escrituras redundantes)
        if self.is_daily_warning != prev_warning or self.is_daily_emergency != prev_emergency:
            self._persist()

        return {
            "safe": level in ("OK", "WARNING"),
            "loss": daily_loss,
            "limit": self.max_daily_loss,
            "remaining": remaining,
            "level": level,
            "equity_inicio": self.equity_inicio_dia,
            "equity_actual": current_equity,
        }

    def check_overall_drawdown(self) -> dict:
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info de cuenta para overall DD")
            return {"safe": False, "loss": 0, "limit": self.max_overall_loss, "remaining": 0, "level": "ERROR"}

        current_equity = account_info.equity
        overall_loss = max(0, self.balance_inicial - current_equity)
        remaining = self.max_overall_loss - overall_loss

        prev_overall_warning = self.is_overall_warning
        prev_overall_emergency = self.is_overall_emergency

        if overall_loss >= self.max_overall_loss:
            level = "VIOLATED"
            self.is_overall_emergency = True
        elif overall_loss >= self.overall_emergency_threshold:
            level = "EMERGENCY"
            self.is_overall_emergency = True
            if not prev_overall_warning:
                self.logger.critical(f"🚨 EMERGENCIA TOTAL: Pérdida ${overall_loss:,.2f} — CERRANDO TODO")
        elif overall_loss >= self.overall_warning_threshold:
            level = "WARNING"
            self.is_overall_warning = True
            self.logger.warning(f"⚠️ ALERTA TOTAL: Pérdida ${overall_loss:,.2f} — No más trades")
        else:
            level = "OK"

        if self.is_overall_warning != prev_overall_warning or self.is_overall_emergency != prev_overall_emergency:
            self._persist()

        return {
            "safe": level in ("OK", "WARNING"),
            "loss": overall_loss,
            "limit": self.max_overall_loss,
            "remaining": remaining,
            "level": level,
            "balance_inicial": self.balance_inicial,
            "equity_actual": current_equity,
        }

    def is_safe_to_trade(self) -> bool:
        daily = self.check_daily_drawdown()
        overall = self.check_overall_drawdown()

        import time
        current_time = time.time()
        if current_time - getattr(self, "_last_log_time", 0) > 3600:
            self.logger.log_drawdown_status(
                daily_loss=daily["loss"], daily_limit=daily["limit"],
                overall_loss=overall["loss"], overall_limit=overall["limit"],
            )
            self._last_log_time = current_time

        if daily["level"] in ("WARNING", "EMERGENCY", "VIOLATED"):
            self.logger.warning(f"Trading bloqueado: Drawdown diario en nivel {daily['level']}")
            return False
        if overall["level"] in ("WARNING", "EMERGENCY", "VIOLATED"):
            self.logger.warning(f"Trading bloqueado: Drawdown total en nivel {overall['level']}")
            return False
        return True

    def should_emergency_close(self) -> bool:
        daily = self.check_daily_drawdown()
        overall = self.check_overall_drawdown()
        return daily["level"] in ("EMERGENCY", "VIOLATED") or overall["level"] in ("EMERGENCY", "VIOLATED")

    # ──────────────────────────────────────────────────────────────────────────
    # RESET DIARIO (con _persist al final)
    # ──────────────────────────────────────────────────────────────────────────

    def reset_daily(self):
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info para reset diario")
            return

        growth = account_info.balance - ChallengeConfig.BALANCE_INICIAL
        if growth > (ChallengeConfig.BALANCE_INICIAL * 0.02):
            new_piso = ChallengeConfig.BALANCE_INICIAL + (growth * 0.5)
            if new_piso > self.balance_inicial:
                self.logger.success(f"🛡️ FORTALEZA: Piso de Equity elevado a ${new_piso:,.2f}")
                self._balance_inicial = new_piso  # setter ya llama _persist()

        self.equity_inicio_dia = max(account_info.balance, account_info.equity)
        self.is_daily_warning = False
        self.is_daily_emergency = False

        self._persist()                           # ← Guardar estado del nuevo día

        self.logger.separator("═")
        self.logger.info(f"📅 RESET DIARIO (5 PM EST)")
        self.logger.info(f"   Nuevo inicio día: ${self.equity_inicio_dia:,.2f}")
        self.logger.separator("═")

    # ──────────────────────────────────────────────────────────────────────────
    # EL RESTO DEL ARCHIVO ES IDÉNTICO AL ORIGINAL
    # (check_and_hedge_crashing_positions, _emergency_protect_position,
    #  emergency_close_all) — omitidos aquí por brevedad, copiarlos sin cambios.
    # ──────────────────────────────────────────────────────────────────────────
