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
from core.llm_oracle import GeminiOracle  # Inyectando Inteligencia Institucional al Riesgo


class TrailingStopManager:
    """
    Gestiona trailing stops para posiciones abiertas.
    Solo modifica posiciones del bot (filtrado por magic number).
    Ahora utiliza la IA (Gemini) para validar si es el momento
    correcto estructuralmente para mover el precio a Break Even o T-Stop.
    """

    def __init__(self, logger: BotLogger, oracle: GeminiOracle = None):
        self.logger = logger
        self.oracle = oracle  # Referencia al CIO de Riesgo AI
        self.enabled = BotConfig.TRAILING_STOP_ENABLED
        self.activation_pips = BotConfig.TRAILING_ACTIVATION_PIPS
        self.step_pips = BotConfig.TRAILING_STEP_PIPS
        self.partial_closes_done = set()

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

        # SMC Partial Close Logic (RR 1:1)
        if position.ticket not in self.partial_closes_done and position.sl != 0.0:
            risk_pips = abs(position.price_open - position.sl) / pip_in_points
            profit_pips_temp = 0.0
            if position.type == mt5.ORDER_TYPE_BUY:
                profit_pips_temp = (tick.bid - position.price_open) / pip_in_points
            else:
                profit_pips_temp = (position.price_open - tick.ask) / pip_in_points
                
            if profit_pips_temp >= risk_pips and risk_pips > 5.0: # Mínimo 5 pips de riesgo para evitar ruido
                self._execute_partial_close(position, tick)
                # Retornamos para evitar modificar el SL simultáneamente con la lógica tradicional en este tick
                return

        point = symbol_info.point
        pip_in_points = 10 * point  # 1 pip = 10 points (5 dígitos)

        tick = mt5.symbol_info_tick(position.symbol)
        if tick is None:
            return

        # ─── Calcular ganancia actual en pips ────────────────────────
        profit_pips = 0.0
        current_price = 0.0
        order_type_str = ""

        if position.type == mt5.ORDER_TYPE_BUY:
            current_price = tick.bid
            profit_pips = (current_price - position.price_open) / pip_in_points
            order_type_str = "BUY"
            new_math_sl = current_price - (self.step_pips * pip_in_points)
        elif position.type == mt5.ORDER_TYPE_SELL:
            current_price = tick.ask
            profit_pips = (position.price_open - current_price) / pip_in_points
            order_type_str = "SELL"
            new_math_sl = current_price + (self.step_pips * pip_in_points)

        # ─── 🧠 MODO IA: CONSULTA ESTRUCTURAL AL ORÁCULO ─────────────
        if profit_pips >= self.activation_pips:
            # Por defecto, la matemática básica aprueba mover el SL
            ai_approved = True 
            ai_reason = "Trailing Matemático Básico"
            new_sl = new_math_sl
            
            # Si el Oráculo está vivo, le preguntamos si es conveniente proteger ahora
            # basado en la estructura institucional (ej. no asfixiar el trade si hay inercia)
            if self.oracle and self.oracle.enabled:
                eval_result = self.oracle.evaluate_exit(position.symbol, profit_pips, order_type_str)
                decision = eval_result.get("decision", "HOLD")
                ai_reason = eval_result.get("reason", "Fallback IA")
                
                if decision == "CLOSE":
                    # La IA ve peligro inminente (Soporte/Resistencia Fuerte)
                    # En lugar de cerrar todo el trade bruscamente, ajustamos el Trailing Stop al máximo
                    # para ahogar la posición (Casi Take Profit dinámico)
                    self.logger.warning(f"🧠 CIO ALERTA en {position.symbol}: {ai_reason}. Asfixiando Trade (Max Protection).")
                    if position.type == mt5.ORDER_TYPE_BUY:
                        new_sl = current_price - (1.5 * pip_in_points) # Aprieta a 1.5 pips de distancia para evitar MT5 Error 10016
                    else:
                        new_sl = current_price + (1.5 * pip_in_points)
                        
                elif decision == "HOLD":
                    # La IA dice "El Trade está sano, déjalo respirar. El trend H1 nos protege".
                    # Solo ponemos BREAK EVEN (Precio de Entrada), pero NO subimos más el trailing para no ahogarlo prematuramente.
                    if position.sl < position.price_open and position.type == mt5.ORDER_TYPE_BUY:
                         new_sl = position.price_open # BREAK EVEN EXACTO
                         self.logger.info(f"🧠 CIO RELAX en {position.symbol}: {ai_reason}. Fijando solo Break Even (Safe Zone).")
                    elif position.sl > position.price_open and position.type == mt5.ORDER_TYPE_SELL:
                         new_sl = position.price_open # BREAK EVEN EXACTO
                         self.logger.info(f"🧠 CIO RELAX en {position.symbol}: {ai_reason}. Fijando solo Break Even (Safe Zone).")
                    else:
                         ai_approved = False # Ya estamos en B.E o mejor, dejamos respirar.

            # ─── EJECUTAR LA MODIFICACIÓN TÁCTICA ────────────────────
            if ai_approved:
                if position.type == mt5.ORDER_TYPE_BUY and new_sl > position.sl:
                    self._modify_sl(position, new_sl, profit_pips)
                elif position.type == mt5.ORDER_TYPE_SELL and new_sl < position.sl:
                    if position.sl == 0.0 or new_sl < position.sl: # Manejo especial por si venía sin SL
                         self._modify_sl(position, new_sl, profit_pips)

    def _execute_partial_close(self, position, tick):
        """Cierra el 50% de la posición e intenta poner Breakeven"""
        if position.ticket in self.partial_closes_done:
            return
            
        close_volume = position.volume / 2.0
        symbol_info = mt5.symbol_info(position.symbol)
        lot_step = symbol_info.volume_step
        close_volume = round(close_volume / lot_step) * lot_step
        
        if close_volume < symbol_info.volume_min:
            self.partial_closes_done.add(position.ticket) # Es muy pequeño para dividir
            return  
            
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": close_volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask,
            "deviation": BotConfig.DEVIATION,
            "magic": BotConfig.MAGIC_NUMBER,
            "comment": "SMC Scale-Out",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.partial_closes_done.add(position.ticket)
            self.logger.success(f"🎯 SMC Scale-Out: 50% cobrado en Ticket #{position.ticket} ({close_volume} lotes). Moviendo a Breakeven.")
            # Intentar mover a breakeven
            self._modify_sl(position, position.price_open, 0)
        else:
            err = result.comment if result else "Unknown"
            self.logger.error(f"Fallo en Scale-Out tick #{position.ticket}: {err}")

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
