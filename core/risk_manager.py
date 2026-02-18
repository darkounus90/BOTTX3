"""
🛡️ Risk Manager - Gestor de Riesgo
=====================================
Gestiona los límites de drawdown diario y total.
Protección de emergencia proactiva para nunca violar los límites del challenge.
"""

import MetaTrader5 as mt5
from config.settings import ChallengeConfig, BotConfig
from utils.logger import BotLogger


class RiskManager:
    """
    Gestor de riesgo para el TX3 Pro Challenge $50K.

    Drawdown Rules:
    - Daily: 5% ($2,500) calculado desde el mayor valor entre
      balance y equity al inicio del día (5 PM EST reset).
    - Overall: 10% ($5,000) ESTÁTICO desde balance inicial.
      NO es trailing — el piso siempre es $45,000.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger

        # Límites del challenge
        self.balance_inicial = ChallengeConfig.BALANCE_INICIAL
        self.max_daily_loss = ChallengeConfig.MAX_DAILY_DRAWDOWN
        self.max_overall_loss = ChallengeConfig.MAX_OVERALL_DRAWDOWN

        # Umbral del día: se actualiza al resetear (5 PM EST)
        self.equity_inicio_dia = ChallengeConfig.BALANCE_INICIAL

        # Umbrales de emergencia (cerrar antes de violar límites)
        self.daily_warning_threshold = (
            self.max_daily_loss * BotConfig.DAILY_DD_WARNING_PCT / 100
        )
        self.daily_emergency_threshold = (
            self.max_daily_loss * BotConfig.DAILY_DD_EMERGENCY_PCT / 100
        )
        self.overall_warning_threshold = (
            self.max_overall_loss * BotConfig.OVERALL_DD_WARNING_PCT / 100
        )
        self.overall_emergency_threshold = (
            self.max_overall_loss * BotConfig.OVERALL_DD_EMERGENCY_PCT / 100
        )

        # Estado
        self.is_daily_warning = False
        self.is_daily_emergency = False
        self.is_overall_warning = False
        self.is_overall_emergency = False

        self.logger.risk(
            f"Risk Manager inicializado | "
            f"Daily Max: ${self.max_daily_loss:,.0f} | "
            f"Overall Max: ${self.max_overall_loss:,.0f}"
        )

    # ─── Verificaciones de Drawdown ───────────────────────────────────

    def check_daily_drawdown(self) -> dict:
        """
        Verifica el drawdown diario.
        El límite se calcula desde el mayor valor entre balance y equity
        al inicio del día (se resetea a las 5 PM EST).

        Returns:
            dict con keys: safe, loss, limit, remaining, level
            level puede ser: 'OK', 'WARNING', 'EMERGENCY', 'VIOLATED'
        """
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info de cuenta para daily DD")
            return {
                "safe": False,
                "loss": 0,
                "limit": self.max_daily_loss,
                "remaining": 0,
                "level": "ERROR",
            }

        current_equity = account_info.equity
        daily_loss = max(0, self.equity_inicio_dia - current_equity)
        remaining = self.max_daily_loss - daily_loss

        # Determinar nivel
        if daily_loss >= self.max_daily_loss:
            level = "VIOLATED"
            self.is_daily_emergency = True
        elif daily_loss >= self.daily_emergency_threshold:
            level = "EMERGENCY"
            self.is_daily_emergency = True
            if not self.is_daily_warning:
                self.logger.critical(
                    f"🚨 EMERGENCIA DIARIA: Pérdida ${daily_loss:,.2f} "
                    f"(85% del límite) — CERRANDO TODO"
                )
        elif daily_loss >= self.daily_warning_threshold:
            level = "WARNING"
            self.is_daily_warning = True
            self.logger.warning(
                f"⚠️ ALERTA DIARIA: Pérdida ${daily_loss:,.2f} "
                f"(70% del límite) — No más trades"
            )
        else:
            level = "OK"

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
        """
        Verifica el drawdown total.
        Es ESTÁTICO: siempre se calcula desde el balance inicial ($50,000).
        El piso de equity es $45,000.

        Returns:
            dict con keys: safe, loss, limit, remaining, level
        """
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info de cuenta para overall DD")
            return {
                "safe": False,
                "loss": 0,
                "limit": self.max_overall_loss,
                "remaining": 0,
                "level": "ERROR",
            }

        current_equity = account_info.equity
        overall_loss = max(0, self.balance_inicial - current_equity)
        remaining = self.max_overall_loss - overall_loss

        # Determinar nivel
        if overall_loss >= self.max_overall_loss:
            level = "VIOLATED"
            self.is_overall_emergency = True
        elif overall_loss >= self.overall_emergency_threshold:
            level = "EMERGENCY"
            self.is_overall_emergency = True
            if not self.is_overall_warning:
                self.logger.critical(
                    f"🚨 EMERGENCIA TOTAL: Pérdida ${overall_loss:,.2f} "
                    f"(85% del límite) — CERRANDO TODO"
                )
        elif overall_loss >= self.overall_warning_threshold:
            level = "WARNING"
            self.is_overall_warning = True
            self.logger.warning(
                f"⚠️ ALERTA TOTAL: Pérdida ${overall_loss:,.2f} "
                f"(70% del límite) — No más trades"
            )
        else:
            level = "OK"

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
        """
        Verifica que sea seguro abrir nuevas operaciones.
        Retorna False si cualquier nivel de drawdown está en WARNING o peor.
        """
        daily = self.check_daily_drawdown()
        overall = self.check_overall_drawdown()

        # Log del estado
        self.logger.log_drawdown_status(
            daily_loss=daily["loss"],
            daily_limit=daily["limit"],
            overall_loss=overall["loss"],
            overall_limit=overall["limit"],
        )

        # No permitir nuevos trades si hay WARNING (proactivo)
        if daily["level"] in ("WARNING", "EMERGENCY", "VIOLATED"):
            self.logger.warning(
                f"Trading bloqueado: Drawdown diario en nivel {daily['level']}"
            )
            return False

        if overall["level"] in ("WARNING", "EMERGENCY", "VIOLATED"):
            self.logger.warning(
                f"Trading bloqueado: Drawdown total en nivel {overall['level']}"
            )
            return False

        return True

    def should_emergency_close(self) -> bool:
        """
        Verifica si se debe hacer un cierre de emergencia de TODAS las posiciones.
        Se activa al 85% de cualquier límite de drawdown.
        """
        daily = self.check_daily_drawdown()
        overall = self.check_overall_drawdown()

        return daily["level"] in ("EMERGENCY", "VIOLATED") or overall["level"] in (
            "EMERGENCY",
            "VIOLATED",
        )

    def emergency_close_all(self) -> int:
        """
        Cierra TODAS las posiciones abiertas de emergencia.
        Returns: número de posiciones cerradas.
        """
        self.logger.critical("🚨🚨🚨 CIERRE DE EMERGENCIA ACTIVADO 🚨🚨🚨")

        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            self.logger.info("No hay posiciones abiertas para cerrar")
            return 0

        closed_count = 0
        for pos in positions:
            # Solo cerrar posiciones del bot
            if pos.magic != BotConfig.MAGIC_NUMBER:
                continue

            # Determinar tipo de cierre
            if pos.type == mt5.ORDER_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                close_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,
                "price": price,
                "deviation": BotConfig.DEVIATION,
                "magic": BotConfig.MAGIC_NUMBER,
                "comment": "EMERGENCY_CLOSE",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.success(
                    f"Posición {pos.ticket} ({pos.symbol}) cerrada de emergencia"
                )
                closed_count += 1
            else:
                error_msg = result.comment if result else "Unknown error"
                self.logger.error(
                    f"Error cerrando posición {pos.ticket}: {error_msg}"
                )

        self.logger.critical(f"Cerradas {closed_count}/{len(positions)} posiciones")
        return closed_count

    # ─── Reset Diario ─────────────────────────────────────────────────

    def reset_daily(self):
        """
        Resetea el tracking diario.
        Se llama a las 5 PM EST cuando TX3 resetea el día.
        """
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info para reset diario")
            return

        # El drawdown diario se calcula desde el MAYOR valor entre balance y equity
        self.equity_inicio_dia = max(account_info.balance, account_info.equity)

        # Reset flags
        self.is_daily_warning = False
        self.is_daily_emergency = False

        self.logger.separator("═")
        self.logger.info(f"📅 RESET DIARIO (5 PM EST)")
        self.logger.info(f"   Nuevo inicio día: ${self.equity_inicio_dia:,.2f}")
        self.logger.separator("═")
