"""
🔄 Trailing Stop Manager
==========================
Mueve el stop loss dinámicamente para proteger ganancias.

Lógica:
1. Cuando una posición alcanza +15 pips de ganancia → se activa el trailing
2. Cada +5 pips adicionales → el SL se mueve al nivel anterior
3. Nunca mueve el SL hacia atrás (solo protege más ganancia)
"""

import MetaTrader5 as mt5
from config.settings import BotConfig
from utils.logger import BotLogger


class TrailingStopManager:
    """
    Gestiona trailing stops para posiciones abiertas.
    Solo modifica posiciones del bot (filtrado por magic number).
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.enabled = BotConfig.TRAILING_STOP_ENABLED
        self.activation_pips = BotConfig.TRAILING_ACTIVATION_PIPS
        self.step_pips = BotConfig.TRAILING_STEP_PIPS

        if self.enabled:
            self.logger.info(
                f"🔄 Trailing Stop activado | "
                f"Activación: +{self.activation_pips} pips | "
                f"Step: {self.step_pips} pips"
            )

    def update_trailing_stops(self):
        """
        Revisa y actualiza los trailing stops de todas las posiciones abiertas.
        Se llama en cada iteración del loop principal.
        """
        if not self.enabled:
            return

        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            # Solo posiciones del bot
            if pos.magic != BotConfig.MAGIC_NUMBER:
                continue

            self._update_position_trailing(pos)

    def _update_position_trailing(self, position):
        """Actualiza el trailing stop de una posición específica"""
        symbol_info = mt5.symbol_info(position.symbol)
        if symbol_info is None:
            return

        point = symbol_info.point
        pip_in_points = 10 * point  # 1 pip = 10 points (5 dígitos)

        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            return

        # ─── Calcular ganancia actual en pips ────────────────────────
        if position.type == mt5.ORDER_TYPE_BUY:
            current_price = tick.bid
            profit_pips = (current_price - position.price_open) / pip_in_points
            # Nuevo SL: precio actual - step_pips
            new_sl = current_price - (self.step_pips * pip_in_points)

            # Solo mover si:
            # 1. La ganancia supera el umbral de activación
            # 2. El nuevo SL es mejor (más alto) que el actual
            if profit_pips >= self.activation_pips and new_sl > position.sl:
                self._modify_sl(position, new_sl, profit_pips)

        elif position.type == mt5.ORDER_TYPE_SELL:
            current_price = tick.ask
            profit_pips = (position.price_open - current_price) / pip_in_points
            # Nuevo SL: precio actual + step_pips
            new_sl = current_price + (self.step_pips * pip_in_points)

            # Solo mover si ganancia suficiente y SL es menor (mejor)
            if profit_pips >= self.activation_pips and new_sl < position.sl:
                self._modify_sl(position, new_sl, profit_pips)

    def _modify_sl(self, position, new_sl: float, current_profit_pips: float):
        """Modifica el stop loss de una posición"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,  # Mantener TP original
            "deviation": BotConfig.DEVIATION,
            "magic": BotConfig.MAGIC_NUMBER,
        }

        result = mt5.order_send(request)

        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.logger.success(
                f"🔄 Trailing SL actualizado | "
                f"Ticket #{position.ticket} ({position.symbol}) | "
                f"SL: {position.sl:.5f} → {new_sl:.5f} | "
                f"Profit: +{current_profit_pips:.1f} pips"
            )
        else:
            error = result.comment if result else "Unknown"
            self.logger.error(
                f"Error actualizando trailing SL #{position.ticket}: {error}"
            )

    def get_trailing_status(self) -> list[dict]:
        """Retorna el estado de trailing de todas las posiciones"""
        statuses = []
        positions = mt5.positions_get()
        if positions is None:
            return statuses

        for pos in positions:
            if pos.magic != BotConfig.MAGIC_NUMBER:
                continue

            symbol_info = mt5.symbol_info(pos.symbol)
            if symbol_info is None:
                continue

            point = symbol_info.point
            pip_in_points = 10 * point
            tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                continue

            if pos.type == mt5.ORDER_TYPE_BUY:
                profit_pips = (tick.bid - pos.price_open) / pip_in_points
            else:
                profit_pips = (pos.price_open - tick.ask) / pip_in_points

            statuses.append({
                "ticket": pos.ticket,
                "symbol": pos.symbol,
                "type": "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL",
                "profit_pips": profit_pips,
                "current_sl": pos.sl,
                "current_tp": pos.tp,
                "trailing_active": profit_pips >= self.activation_pips,
            })

        return statuses
