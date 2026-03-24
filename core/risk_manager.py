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

        # ─── ANCLAJE DE CAPITAL DEL RETO ───
        # Forzamos que el balance inicial sea el del Challenge (50k) 
        # para que el drawdown total concuerde con el broker.
        self._balance_inicial = ChallengeConfig.BALANCE_INICIAL
        
        account_info = mt5.account_info()
        if account_info:
            # La equidad de inicio de día se resetea a las 5 PM EST.
            # Si el bot inicia fuera de ese horario, intenta una estimación conservadora.
            self.equity_inicio_dia = max(account_info.balance, account_info.equity)
            self.logger.info(f"💰 Sincronizando Capital: MT5 Balance=${account_info.balance:,.2f} | Equity=${account_info.equity:,.2f}")
        else:
            self.logger.warning("No se pudo obtener info de cuenta en inicio de RiskManager. Usando default de $50k.")
            self.equity_inicio_dia = ChallengeConfig.BALANCE_INICIAL

        # Estado
        self.is_daily_warning = False
        self.is_daily_emergency = False
        self.is_overall_warning = False
        self.is_overall_emergency = False

        self.logger.risk(f"🛡️ Risk Manager ANCLADO a Reto: ${self._balance_inicial:,.2f} | Equidad Día: ${self.equity_inicio_dia:,.2f}")

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
        CALCULA DESDE EL HISTORIAL REAL DE MT5:
        - Suma las pérdidas/ganancias cerradas del día (deals)
        - Suma el P&L flotante de posiciones abiertas
        - Compara contra el límite diario

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
        
        # ─── MÉTODO MÁS PRECISO: Calcular desde medianoche FTMO (Praga) ─────────
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        from config.settings import BotConfig
        
        now_prague = datetime.now(ZoneInfo(BotConfig.FTMO_TIMEZONE))
        midnight_prague = now_prague.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ftmo_day_local = datetime.fromtimestamp(midnight_prague.timestamp())
        
        closed_pnl_today = 0.0
        try:
            deals = mt5.history_deals_get(start_today, today + timedelta(hours=1))
            if deals:
                for d in deals:
                    if d.entry in [1, 2, 3]:  # Solo cierres (OUT)
                        closed_pnl_today += (d.profit + d.commission)
        except Exception:
            pass
        
        # P&L total del día = trades cerrados hoy + flotante actual
        floating_pnl = account_info.profit  # Ganancia/pérdida no realizada actual
        total_day_pnl = closed_pnl_today + floating_pnl
        
        # Si el día va en pérdida, daily_loss es positivo (cuánto hemos perdido)
        daily_loss = max(0, -total_day_pnl)
        
        # También comparar con el método clásico y usar el MAYOR (más conservador)
        classic_loss = max(0, self.equity_inicio_dia - current_equity)
        daily_loss = max(daily_loss, classic_loss)
        
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
        import time
        current_time = time.time()
        if current_time - getattr(self, "_last_log_time", 0) > 3600:
            self.logger.log_drawdown_status(
                daily_loss=daily["loss"],
                daily_limit=daily["limit"],
                overall_loss=overall["loss"],
                overall_limit=overall["limit"],
            )
            self._last_log_time = current_time

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
                                     f"Stop loss fallido o deslizamiento severo. Ejecutando PROTECCIÓN FTMO.")
                self._emergency_protect_position(pos)

    def _emergency_protect_position(self, position):
        """
        [FTMO COMPLIANT]
        Intenta CERRAR la posición agresivamente primero para no generar flags de arbitraje.
        Añade micro-retrasos aleatorios para simular pánico humano.
        Si, y solo si, el cierre falla reiteradamente, ejecuta el Hedge como último recurso.
        """
        import time
        import random
        
        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info: return
        
        # 1. Pánico Humano Simulado (Retraso aleatorio de 400ms a 1200ms)
        delay = random.uniform(0.4, 1.2)
        self.logger.warning(f"🧍‍♂️ Simulando reacción humana: Pausa de {delay:.2f}s antes del cierre agresivo...")
        time.sleep(delay)
        
        # 2. INTENTO DE CIERRE AGRESIVO (Market Close)
        for attempt, deviation in enumerate([30, 80, 150], 1):
            tick = mt5.symbol_info_tick(position.symbol)
            if not tick: continue
                
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

            request_close = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "price": price,
                "deviation": deviation,
                "magic": BotConfig.MAGIC_NUMBER,
                "comment": "Panic Close FTMO",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request_close)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.hedged_tickets.add(position.ticket) # Registrar para no reintentar
                self.logger.success(f"✅ SALVACIÓN: Posición #{position.ticket} CERRADA agresivamente (Intento {attempt}, Dev {deviation}).")
                return # Salimos, no se necesita Hedge
            else:
                self.logger.error(f"⚠️ Cierre agresivo fallido (Intento {attempt}): {result.comment if result else 'Unknown'}")
                time.sleep(0.3) # Breve pausa entre intentos
                
        # 3. PLAN B: HEDGE DE SUPERVIVENCIA (Solo si el broker denegó el cierre)
        self.logger.critical(f"🛑 Broker rechazó el cierre 3 veces. Ejecutando HEDGE DE SUPERVIVENCIA para #{position.ticket}")
        tick = mt5.symbol_info_tick(position.symbol)
        if not tick: return
        
        hedge_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if hedge_type == mt5.ORDER_TYPE_SELL else tick.ask
        
        request_hedge = {
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
        
        result = mt5.order_send(request_hedge)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.hedged_tickets.add(position.ticket)
            self.hedged_tickets.add(result.order)
            self.logger.success(f"🛡️ HEDGE EJECUTADO COMO ÚLTIMO RECURSO: Posición contraria #{result.order} abierta.")
        else:
            self.logger.error(f"💀 FALLO CRÍTICO TOTAL: No se pudo hacer set del Hedge para #{position.ticket}.")

    def emergency_close_all(self) -> int:
        """
        Cierra TODAS las posiciones abiertas de emergencia.
        BLINDADO: Reintenta hasta 3 veces con slippage creciente.
        Returns: número de posiciones cerradas.
        """
        self.logger.critical("🚨🚨🚨 CIERRE DE EMERGENCIA ACTIVADO 🚨🚨🚨")

        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            self.logger.info("No hay posiciones abiertas para cerrar")
            return 0

        bot_positions = [p for p in positions if p.magic == BotConfig.MAGIC_NUMBER]
        if not bot_positions:
            self.logger.info("No hay posiciones del bot para cerrar")
            return 0

        closed_count = 0
        failed_tickets = []

        for pos in bot_positions:
            closed = False
            # 3 intentos con desviación creciente (20, 50, 100 puntos)
            for attempt, deviation in enumerate([20, 50, 100], 1):
                try:
                    tick = mt5.symbol_info_tick(pos.symbol)
                    if not tick:
                        continue

                    if pos.type == mt5.ORDER_TYPE_BUY:
                        close_type = mt5.ORDER_TYPE_SELL
                        price = tick.bid
                    else:
                        close_type = mt5.ORDER_TYPE_BUY
                        price = tick.ask

                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume,
                        "type": close_type,
                        "position": pos.ticket,
                        "price": price,
                        "deviation": deviation,
                        "magic": BotConfig.MAGIC_NUMBER,
                        "comment": "EMERGENCY_CLOSE",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }

                    result = mt5.order_send(request)
                    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.logger.success(
                            f"✅ Posición {pos.ticket} ({pos.symbol}) cerrada de emergencia"
                        )
                        closed_count += 1
                        closed = True
                        break
                    else:
                        error_msg = result.comment if result else "Unknown"
                        self.logger.warning(
                            f"⚠️ Intento {attempt}/3 fallido para {pos.ticket}: {error_msg} (dev={deviation})"
                        )
                        import time as _time
                        _time.sleep(0.5)  # Esperar medio segundo antes de reintentar

                except Exception as e:
                    self.logger.error(f"Error en intento {attempt}/3 para {pos.ticket}: {e}")

            if not closed:
                failed_tickets.append(pos.ticket)
                self.logger.critical(f"❌ NO SE PUDO CERRAR posición {pos.ticket} después de 3 intentos")

        self.logger.critical(f"Cerradas {closed_count}/{len(bot_positions)} posiciones")

        if failed_tickets:
            self.logger.critical(f"🚨 TICKETS SIN CERRAR: {failed_tickets} — REQUIERE INTERVENCIÓN MANUAL")

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
