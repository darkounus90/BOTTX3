"""
📊 Position Manager - Gestor de Posiciones
============================================
Calcula tamaños de posición y ejecuta órdenes con SL/TP obligatorio.
"""

import MetaTrader5 as mt5
from config.settings import ChallengeConfig, BotConfig
from utils.logger import BotLogger


class PositionManager:
    """
    Gestiona el cálculo de posiciones y ejecución de órdenes.
    Todas las órdenes llevan STOP LOSS obligatorio.
    """

    def __init__(self, logger: BotLogger, phase: int, risk_manager=None):
        self.logger = logger
        self.phase = phase
        self.risk_manager = risk_manager
        self.trades_today = 0
        self.max_trades_per_day = BotConfig.MAX_TRADES_PER_DAY

    def _get_atr(self, symbol: str, period: int = 14) -> float:
        """Calcula el ATR (Average True Range) para normalizar por volatilidad"""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, period + 1)
        if rates is None: return 20.0 # Valor default seguro si falla MT5
        
        tr_list = []
        for i in range(1, len(rates)):
            high = rates[i]['high']
            low = rates[i]['low']
            prev_close = rates[i-1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        
        atr_points = sum(tr_list) / len(tr_list)
        # Convertir a pips
        point = mt5.symbol_info(symbol).point
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        return (atr_points / pip_size) if pip_size > 0 else 20.0

    def calculate_position_size(self, symbol: str, stop_loss_pips: float, probability: float = None, portfolio_weight: float = 1.0) -> float | None:
        """
        Calcula el tamaño de posición (FORTALEZA MATEMÁTICA).
        """
        acc = mt5.account_info()
        if not acc: return None

        # ─── 1. ESCALADO ASINTÓTICO (SURVIVAL ENGINE) ───
        # El riesgo se asfixia a medida que te acercas al piso de ruina.
        initial_bal = ChallengeConfig.BALANCE_INICIAL
        limit_pct = ChallengeConfig.MAX_OVERALL_DRAWDOWN_PCT / 100.0
        floor = initial_bal * (1 - limit_pct) # El piso absoluto ($45k)
        
        # 'Distancia a la Ruina' (Buffer de seguridad actual)
        buffer = acc.equity - floor
        max_buffer = initial_bal - floor # Buffer inicial ($5k)
        
        # Factor de supervivencia: ratio 0.0 a 1.0 de cuánto buffer nos queda
        survival_factor = max(0, min(1.0, (buffer / max_buffer)))
        
        # El riesgo base (1%) se multiplica por el factor de supervivencia.
        # Si estás a $500 del suelo, el riesgo cae a un 10%, obligándote a usar micro-lotes.
        risk_pct = BotConfig.MAX_RISK_PER_TRADE_PCT * survival_factor
        
        # ─── 2. ADAPTACIÓN DE VOLATILIDAD (ATR) ───
        # Si el usuario no mandó un SL técnico, calculamos uno basado en el ruido del mercado.
        if stop_loss_pips is None or stop_loss_pips <= 5:
            atr_v = self._get_atr(symbol)
            stop_loss_pips = atr_v * 1.5 # SL = 1.5 veces el aliento del mercado
            self.logger.info(f"📏 Math Fortress: Usando ATR Adaptive SL de {stop_loss_pips:.1f} pips para {symbol}")

        # ─── 3. KELLY IA Y REBALANCEO ───
        if probability is not None:
            kelly = (probability - 50) / 100 + 0.5 # Ajuste suave de Kelly
            risk_pct *= kelly 
        
        risk_pct *= portfolio_weight
        risk_amount = acc.balance * (risk_pct / 100)

        # ─── 4. CÁLCULO DE LOTAJE ───
        si = mt5.symbol_info(symbol)
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        # Pip Value formula: (PipSize / TickSize) * TickValue
        pip_val_lot = (pip_size / si.trade_tick_size) * si.trade_tick_value
        
        lotes = risk_amount / (stop_loss_pips * pip_val_lot)
        lotes = round(lotes / si.volume_step) * si.volume_step
        lotes = max(si.volume_min, min(lotes, si.volume_max))

        self.logger.risk(f"🛡️ MATH FORTRESS: {symbol} | Risk {risk_pct:.3f}% | SL: {stop_loss_pips:.1f} | Lotes: {lotes}")
        return lotes

    def place_order(
        self,
        symbol: str,
        order_type: int,
        stop_loss_pips: float,
        take_profit_pips: float,
        probability: float = None,
        **kwargs
    ) -> dict | None:
        """
        Coloca una orden con STOP LOSS y TAKE PROFIT obligatorios.

        Args:
            symbol: Par de divisas
            order_type: mt5.ORDER_TYPE_BUY o mt5.ORDER_TYPE_SELL
            stop_loss_pips: Distancia del SL en pips
            take_profit_pips: Distancia del TP en pips
            probability: Probabilidad de éxito estimada por la IA (opcional)

        Returns:
            Dict con info de la orden, o None si hay error
        """
        # ─── Verificar límite de trades diarios ──────────────────────
        if self.trades_today >= self.max_trades_per_day:
            self.logger.warning(
                f"Límite de trades diarios alcanzado: "
                f"{self.trades_today}/{self.max_trades_per_day}"
            )
            return None

        # ─── Verificar Risk:Reward mínimo ────────────────────────────
        rr_ratio = take_profit_pips / stop_loss_pips if stop_loss_pips > 0 else 0
        if rr_ratio < BotConfig.MIN_RR_RATIO:
            self.logger.warning(
                f"R:R ratio insuficiente: {rr_ratio:.1f} "
                f"(mínimo: {BotConfig.MIN_RR_RATIO})"
            )
            return None

        # ─── Calcular tamaño de posición ─────────────────────────────
        # Obtenemos kwarg portfolio_weight si viene
        weight = kwargs.get('portfolio_weight', 1.0)
        volume = self.calculate_position_size(symbol, stop_loss_pips, probability, portfolio_weight=weight)
        if volume is None:
            return None

        # ─── Obtener precio actual ───────────────────────────────────
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"No se pudo obtener precio de {symbol}")
            return None

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"No se pudo obtener info de {symbol}")
            return None

        point = symbol_info.point

        # ─── Calcular SL y TP ────────────────────────────────────────
        # 1 pip = 10 points para pares de 5 dígitos
        pip_in_points = 10 * point

        # ─── Validar Spread Dinámico ─────────────────────────────────
        current_spread_pips = (tick.ask - tick.bid) / pip_in_points
        if current_spread_pips > BotConfig.MAX_SPREAD_PIPS:
            self.logger.warning(
                f"⚠️ Operación rechazada: Spread muy alto en {symbol} "
                f"({current_spread_pips:.1f} pips > {BotConfig.MAX_SPREAD_PIPS} max)"
            )
            return None

        if order_type == mt5.ORDER_TYPE_BUY:
            price = tick.ask
            sl = price - (stop_loss_pips * pip_in_points)
            tp = price + (take_profit_pips * pip_in_points)
            order_type_str = "BUY"
        elif order_type == mt5.ORDER_TYPE_SELL:
            price = tick.bid
            sl = price + (stop_loss_pips * pip_in_points)
            tp = price - (take_profit_pips * pip_in_points)
            order_type_str = "SELL"
        else:
            self.logger.error(f"Tipo de orden inválido: {order_type}")
            return None

        # ─── Crear y enviar request ──────────────────────────────────
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": BotConfig.DEVIATION,
            "magic": BotConfig.MAGIC_NUMBER,
            "comment": f"{BotConfig.ORDER_COMMENT_PREFIX}_Phase{self.phase}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None:
            self.logger.error("order_send retornó None")
            return None

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Error en orden: {result.comment} (code: {result.retcode})")
            return None

        # ─── Éxito ───────────────────────────────────────────────────
        self.trades_today += 1

        self.logger.log_order(
            order_type=order_type_str,
            symbol=symbol,
            volume=volume,
            price=price,
            sl=sl,
            tp=tp,
            sl_pips=stop_loss_pips,
            tp_pips=take_profit_pips,
        )
        self.logger.info(
            f"Trades hoy: {self.trades_today}/{self.max_trades_per_day}"
        )

        return {
            "ticket": result.order,
            "type": order_type_str,
            "symbol": symbol,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "rr_ratio": rr_ratio,
        }

    def get_open_positions(self) -> list:
        """Obtiene todas las posiciones abiertas del bot"""
        positions = mt5.positions_get()
        if positions is None:
            return []

        # Filtrar solo posiciones del bot
        bot_positions = [
            pos for pos in positions if pos.magic == BotConfig.MAGIC_NUMBER
        ]

        return bot_positions

    def get_open_positions_count(self) -> int:
        """Retorna el número de posiciones abiertas del bot"""
        return len(self.get_open_positions())

    def check_correlation_shield(self, symbol: str) -> bool:
        """
        Escudo Anti-Correlación Pro (Net Currency Exposure).
        Evita duplicar riesgo en la misma moneda base o cotizada.
        """
        open_positions = self.get_open_positions()
        if not open_positions: return True

        # Extraer monedas del nuevo símbolo (ej: EUR y USD)
        new_base = symbol[:3]
        new_quote = symbol[3:]
        
        for pos in open_positions:
            p_base = pos.symbol[:3]
            p_quote = pos.symbol[3:]
            
            # 1. Bloqueo de Moneda Base (ej: EURUSD y EURJPY)
            if new_base == p_base:
                self.logger.warning(f"🛡️ CORRELACIÓN: Bloqueado {symbol}. Ya tienes exposición BASE en {new_base} ({pos.symbol}).")
                return False
                
            # 2. Bloqueo de Moneda Cotizada (ej: EURUSD y GBPUSD)
            if new_quote == p_quote:
                self.logger.warning(f"🛡️ CORRELACIÓN: Bloqueado {symbol}. Ya tienes exposición QUOTE en {new_quote} ({pos.symbol}).")
                return False

        return True

    def close_position(self, ticket: int) -> bool:
        """
        Cierra una posición específica por ticket.

        Args:
            ticket: Número de ticket de la posición

        Returns:
            True si se cerró exitosamente
        """
        # Buscar la posición
        positions = mt5.positions_get(ticket=ticket)
        if positions is None or len(positions) == 0:
            self.logger.error(f"Posición {ticket} no encontrada")
            return False

        pos = positions[0]

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
            "comment": "CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            profit = pos.profit
            self.logger.success(
                f"Posición {ticket} cerrada | "
                f"{pos.symbol} | P&L: ${profit:+,.2f}"
            )
            return True
        else:
            error_msg = result.comment if result else "Unknown"
            self.logger.error(f"Error cerrando {ticket}: {error_msg}")
            return False

    def reset_daily(self):
        """Resetea el contador diario de trades"""
        self.trades_today = 0
        self.logger.info(f"Contador de trades diarios reseteado")
        
    def manage_hedging(self):
        """
        Cobertura Silenciosa (Hedging).
        Escanea si algún trade está perdiendo más del 80% de la distancia a su Stop Loss.
        Si es así, en lugar de aceptar la pérdida, abre una operación contraria 
        del mismo lotaje para congelar (Hedge) la equidad.
        """
        if not getattr(BotConfig, "HEDGING_ENABLED", False):
            return
            
        open_positions = self.get_open_positions()
        if not open_positions:
            return
            
        for pos in open_positions:
            # Si en en el commentario hay 'HEDGE' ignoramos para no atraparnos en bucle
            if "HEDGE" in pos.comment:
                continue
                
            entry_price = pos.price_open
            sl_price = pos.sl
            current_price = mt5.symbol_info_tick(pos.symbol).bid if pos.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(pos.symbol).ask
            
            if sl_price == 0:
                continue
                
            total_risk_dist = abs(entry_price - sl_price)
            current_loss_dist = entry_price - current_price if pos.type == mt5.ORDER_TYPE_BUY else current_price - entry_price

            if total_risk_dist > 0:
                loss_pct = current_loss_dist / total_risk_dist
                
                # Si estamos al 80% del SL en pérdida
                if loss_pct >= 0.80 and pos.profit < 0:
                    self.logger.critical(f"🛡️ HEDGING DE EMERGENCIA: Posición #{pos.ticket} ({pos.symbol}) en 80% de riesgo.")
                    
                    hedge_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    price_h = mt5.symbol_info_tick(pos.symbol).bid if hedge_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": pos.symbol,
                        "volume": pos.volume, # Mismo lotaje
                        "type": hedge_type,
                        "price": price_h,
                        "sl": 0.0, # Congelado sin SL temporalmente
                        "tp": 0.0,
                        "deviation": BotConfig.DEVIATION,
                        "magic": BotConfig.MAGIC_NUMBER,
                        "comment": f"HEDGE_P{self.phase}_T{pos.ticket}",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    res = mt5.order_send(request)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        self.logger.success(f"✅ Cobertura Silenciosa Ejecutada. Pérdida congelada en {pos.symbol}.")
                        
                        # Modificamos la posición original para quitarle el SL y que no salte
                        req_modify = {
                             "action": mt5.TRADE_ACTION_SLTP,
                             "position": pos.ticket,
                             "symbol": pos.symbol,
                             "sl": 0.0,
                             "tp": 0.0,
                             "magic": BotConfig.MAGIC_NUMBER
                        }
                        mt5.order_send(req_modify)
