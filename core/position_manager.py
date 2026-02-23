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

    def __init__(self, logger: BotLogger, phase: int):
        self.logger = logger
        self.phase = phase
        self.trades_today = 0
        self.max_trades_per_day = BotConfig.MAX_TRADES_PER_DAY

    def calculate_position_size(self, symbol: str, stop_loss_pips: float, probability: float = None) -> float | None:
        """
        Calcula el tamaño de posición basado en:
        - Riesgo máximo: 0.5% del balance por trade (O Kelly Criterion dinámico)
        - Stop loss en pips

        Args:
            symbol: Par de divisas (e.g., "EURUSD")
            stop_loss_pips: Distancia del stop loss en pips
            probability: Probabilidad de éxito estimada por la IA (opcional)

        Returns:
            Tamaño de posición en lotes, o None si hay error
        """
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener info de cuenta para position sizing")
            return None

        balance = account_info.balance

        # Kelly Criterion dinámico (Position Sizing Inteligente)
        risk_pct = BotConfig.MAX_RISK_PER_TRADE_PCT
        if probability is not None and probability > 0:
            if probability >= 75:
                risk_pct = 1.2  # Alta convicción -> Aumentar riesgo
            elif probability >= 60:
                risk_pct = 0.8  # Buena convicción
            elif probability < 55:
                risk_pct = 0.2  # Dudoso -> Reducir riesgo para proteger capital
            self.logger.info(f"⚖️ Kelly Criterion Activo: Probabilidad {probability:.1f}% -> Ajustando riesgo a {risk_pct}%")

        # Riesgo en dólares
        risk_amount = balance * (risk_pct / 100)

        # Obtener info del símbolo
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Símbolo {symbol} no encontrado")
            return None

        # Valor del pip
        # Para la mayoría de pares forex, 1 pip = 10 * point
        pip_value = symbol_info.trade_tick_value
        if pip_value <= 0:
            self.logger.error(f"Valor del pip inválido para {symbol}: {pip_value}")
            return None

        # Calcular lotes
        if stop_loss_pips <= 0:
            self.logger.error(f"Stop loss inválido: {stop_loss_pips} pips")
            return None

        position_size = risk_amount / (stop_loss_pips * pip_value)

        # Ajustar a los límites del símbolo
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step

        # Redondear al step válido
        position_size = round(position_size / lot_step) * lot_step
        position_size = max(min_lot, min(position_size, max_lot))

        self.logger.trade(f"Position Size calculado:")
        self.logger.trade(f"  Balance:    ${balance:,.2f}")
        self.logger.trade(f"  Riesgo:     ${risk_amount:,.2f} ({risk_pct}%)")
        self.logger.trade(f"  SL Pips:    {stop_loss_pips}")
        self.logger.trade(f"  Lotes:      {position_size:.2f}")

        return position_size

    def place_order(
        self,
        symbol: str,
        order_type: int,
        stop_loss_pips: float,
        take_profit_pips: float,
        probability: float = None,
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
        volume = self.calculate_position_size(symbol, stop_loss_pips, probability)
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
        Escudo Anti-Correlación (Multi-Asset Analysis).
        Evita tener múltiples posiciones que dependan de la misma base macroeconómica.
        """
        open_positions = self.get_open_positions()
        if not open_positions:
            return True

        # Logica ultra rápida para evitar "Risk Cascades" en USD
        has_usd = "USD" in symbol
        
        for pos in open_positions:
            if has_usd and ("USD" in pos.symbol) and (pos.symbol != symbol):
                self.logger.warning(
                    f"🛡️ ESCUDO ANTI-CORRELACIÓN: {symbol} bloqueado porque "
                    f"ya existe una posición abierta en {pos.symbol}. (Se evita acumular USD Risk)"
                )
                return False
                
            # Logica para EUR (Ej evitar EURUSD y EURJPY al mismo tiempo)
            if "EUR" in symbol and ("EUR" in pos.symbol) and (pos.symbol != symbol):
                 self.logger.warning(
                    f"🛡️ ESCUDO ANTI-CORRELACIÓN: {symbol} bloqueado para no exponer doble riesgo en el Euro."
                )
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
