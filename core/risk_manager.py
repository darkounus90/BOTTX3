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

        # Inicializa base, pero los límites se calcularán dinámicamente con las properties
        self._balance_inicial = ChallengeConfig.BALANCE_INICIAL

        # Umbral del día: se actualiza al resetear (5 PM EST)
        self.equity_inicio_dia = ChallengeConfig.BALANCE_INICIAL

        # Estado
        self.is_daily_warning = False
        self.is_daily_emergency = False
        self.is_overall_warning = False
        self.is_overall_emergency = False

        self.logger.risk("Risk Manager inicializado (Modo de Cálculo Dinámico).")

    @property
    def balance_inicial(self):
        return self._balance_inicial

    @balance_inicial.setter
    def balance_inicial(self, value):
        self._balance_inicial = value

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

    def check_and_hedge_crashing_positions(self):
        """
        Escanea todas las posiciones abiertas. Si alguna posición individual
        tiene una pérdida no realizada severa (ej. > 3% de la cuenta), ejecuta un
        Hedge Automático abriendo la posición contraria, congelando la pérdida.
        """
        positions = mt5.positions_get()
        if not positions:
            return

        if not hasattr(self, "hedged_tickets"):
            self.hedged_tickets = set()

        account_info = mt5.account_info()
        if not account_info: return
        
        # Límite dinámico del 3% del balance inicial verificado
        hedge_threshold_amount = self.balance_inicial * 0.03

        for pos in positions:
            if pos.magic != BotConfig.MAGIC_NUMBER: continue
            if pos.ticket in self.hedged_tickets: continue
            
            # Defensa Stateless: Verificar si el hedge ya está activo pero el bot se reinició (amnesia de memoria)
            has_hedge = any(
                p.symbol == pos.symbol and p.type != pos.type 
                for p in positions 
                if p.magic == BotConfig.MAGIC_NUMBER
            )
            
            if has_hedge:
                self.hedged_tickets.add(pos.ticket) # Registrar retrospectivamente
                continue
                
            profit = pos.profit
            if profit < -hedge_threshold_amount:
                self.logger.critical(f"🦢💥 CISNE NEGRO DETECTADO 💥🦢: Posición #{pos.ticket} perdiendo ${-profit:.2f}. "
                                     f"Stop loss fallido o deslizamiento severo. Ejecutando HEDGE DE EMERGENCIA.")
                self._emergency_hedge_position(pos)

    def _emergency_hedge_position(self, position):
        """Abre una orden contraria idéntica para congelar el PnL"""
        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info: return
        tick = mt5.symbol_info_tick(position.symbol)
        if not tick: return
        
        hedge_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if hedge_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": hedge_type,
            "price": price,
            "deviation": BotConfig.DEVIATION,
            "magic": BotConfig.MAGIC_NUMBER,
            "comment": f"Auto-Hedge #{position.ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.hedged_tickets.add(position.ticket) # El ticket original ahora está protegido
            self.hedged_tickets.add(result.order) # Registrar la pata del hedge para evitar bucles
            self.logger.success(f"🛡️ HEDGE EJECUTADO: Posición contraria #{result.order} abierta con {position.volume} lotes en {position.symbol}.")
        else:
            err = result.comment if result else "Unknown"
            self.logger.error(f"Fallo crítico ejecutando Hedge para #{position.ticket}: {err}")

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

        # ─── FORTALEZA MATEMÁTICA: EQUITY LOCK ───
        # Si hemos ganado > 2%, subimos el 'piso' para proteger el capital inicial.
        # Esto evita que una racha mala después de una buena nos devuelva al drawdown original.
        growth = account_info.balance - ChallengeConfig.BALANCE_INICIAL
        if growth > (ChallengeConfig.BALANCE_INICIAL * 0.02):
             # Bloqueamos el 50% de la ganancia como nuevo 'suelo' inviolable
             new_piso = ChallengeConfig.BALANCE_INICIAL + (growth * 0.5)
             if new_piso > self.balance_inicial:
                 self.logger.success(f"🛡️ FORTALEZA: Piso de Equity elevado a ${new_piso:,.2f} (Protegiendo Ganancias)")
                 self.balance_inicial = new_piso

        # El drawdown diario se calcula desde el MAYOR valor entre balance y equity
        self.equity_inicio_dia = max(account_info.balance, account_info.equity)

        # Reset flags
        self.is_daily_warning = False
        self.is_daily_emergency = False

        self.logger.separator("═")
        self.logger.info(f"📅 RESET DIARIO (5 PM EST)")
        self.logger.info(f"   Nuevo inicio día: ${self.equity_inicio_dia:,.2f}")
        self.logger.separator("═")
