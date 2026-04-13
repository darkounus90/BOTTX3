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

    def _get_atr_pips(self, symbol: str, period: int = 14) -> float:
        """Calcula el ATR en pips para el blindaje dinámico"""
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, period + 1)
        if rates is None: return 20.0
        tr_list = []
        for i in range(1, len(rates)):
            high = rates[i]['high']
            low = rates[i]['low']
            prev_close = rates[i-1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        atr_points = sum(tr_list) / len(tr_list)
        pip_size = 0.01 if "JPY" in symbol else 0.0001
        return (atr_points / pip_size) if pip_size > 0 else 20.0

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

        # ─── DINÁMICA DE PIPs ───
        point = symbol_info.point
        # Normalización Universal de Pip (Forex, Oro, Índices)
        if symbol_info.digits in [3, 5]:
            pip_in_points = 10 * point
        elif symbol_info.digits == 2: # Oro (XAUUSD)
            pip_in_points = 0.10 # 1 pip = 0.10 USD
        else: # 4 dígitos o Índices
            pip_in_points = point

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

        # 🛡️ PILAR 3: Blindaje Automático Preventivo (Break Even a 1x ATR)
        atr_pips = self._get_atr_pips(position.symbol)
        if profit_pips >= atr_pips:
            be_pip = 1.0 # 1 pip para cubrir comisiones de ida y vuelta
            if position.type == mt5.ORDER_TYPE_BUY:
                be_price = position.price_open + (be_pip * pip_in_points)
                # MITIGACIÓN 2: Modificación atómica, evitamos Spam 10013 alertando solo cambios significativos.
                if position.sl < be_price and abs(position.sl - be_price) > (0.5 * pip_in_points):
                    self.logger.success(f"🛡️ BLINDAJE 1x ATR: {position.symbol} asegura {be_pip} pips de BE. Riesgo de Pérdida Eliminado.")
                    self._modify_sl(position, be_price, current_profit_pips=profit_pips)
                    return
            elif position.type == mt5.ORDER_TYPE_SELL:
                be_price = position.price_open - (be_pip * pip_in_points)
                if (position.sl == 0.0 or position.sl > be_price) and (position.sl == 0.0 or abs(position.sl - be_price) > (0.5 * pip_in_points)):
                    self.logger.success(f"🛡️ BLINDAJE 1x ATR: {position.symbol} asegura {be_pip} pips de BE. Riesgo de Pérdida Eliminado.")
                    self._modify_sl(position, be_price, current_profit_pips=profit_pips)
                    return

        # Por defecto, la matemática básica aprueba mover el SL solo si ya pasó pips de activación
        ai_approved = (profit_pips >= self.activation_pips)
        ai_reason = "Trailing Matemático Básico"
        new_sl = new_math_sl if ai_approved else position.sl
        
        # ─── 🧠 MODO IA: ESCÁNER PREVENTIVO DEL ORÁCULO ─────────────
        # La IA evalúa operaciones vivas, pero con INTELIGENCIA INSTITUCIONAL:
        # 1. PERÍODO DE GRACIA: 10 minutos para que respire (antes 5)
        # 2. UMBRAL DE RUIDO: Solo activar asfixia si el trade pierde más de 5 pips (antes 3)
        # 3. PROTECCIÓN MÍNIMA: SL de asfixia a 7 pips de distancia (antes 5)
        if self.oracle and self.oracle.enabled:
            import time
            now_ts = time.time()
            
            # ─── PERÍODO DE GRACIA: 10 minutos después de abrir ─────────
            trade_age_seconds = now_ts - position.time
            GRACE_PERIOD_SECONDS = 600  # 10 minutos
            
            if trade_age_seconds < GRACE_PERIOD_SECONDS:
                grace_log_key = f"_grace_logged_{position.ticket}"
                if not getattr(self, grace_log_key, False):
                    remaining = int((GRACE_PERIOD_SECONDS - trade_age_seconds) / 60)
                    self.logger.info(f"⏳ Gracia IA: {position.symbol} Ticket #{position.ticket} | {remaining} min restantes.")
                    setattr(self, grace_log_key, True)
                ai_approved = False
            else:
                last_ai_time = getattr(self, f"_last_ai_time_{position.symbol}", 0)
                
                # Rate limit: 120 segundos por símbolo
                if now_ts - last_ai_time > 120:
                    eval_result = self.oracle.evaluate_exit(position.symbol, profit_pips, order_type_str)
                    setattr(self, f"_last_ai_eval_{position.symbol}", eval_result)
                    setattr(self, f"_last_ai_time_{position.symbol}", now_ts)
                else:
                    eval_result = getattr(self, f"_last_ai_eval_{position.symbol}", {"decision": "HOLD", "reason": "Enfriamiento IA"})

                decision = eval_result.get("decision", "HOLD")
                ai_reason = eval_result.get("reason", "Fallback IA")
                
                if decision == "CLOSE":
                    # Umbral de Ruido: Solo intervenir si la pérdida es > 5 pips o ganancia devuelta > 8 pips
                    if profit_pips < -5.0 or profit_pips >= 8.0:
                        ai_approved = True
                        
                        last_log_time = getattr(self, f"_last_log_time_{position.symbol}", 0)
                        if now_ts - last_log_time > 30:
                            self.logger.warning(f"🧠 CIO ALERTA ROJA en {position.symbol}: {ai_reason}. Asfixiando a 7 pips.")
                            setattr(self, f"_last_log_time_{position.symbol}", now_ts)
                        
                        # SL de protección a 7 pips (más holgado para evitar cacería por Spread)
                        if position.type == mt5.ORDER_TYPE_BUY:
                            new_sl = current_price - (7.0 * pip_in_points)
                            if position.sl != 0.0 and new_sl < position.sl:
                                new_sl = position.sl
                        else:
                            new_sl = current_price + (7.0 * pip_in_points)
                            if position.sl != 0.0 and new_sl > position.sl:
                                new_sl = position.sl
                    else:
                        ai_approved = False
                        last_log_time = getattr(self, f"_last_log_time_{position.symbol}", 0)
                        if now_ts - last_log_time > 60:
                            self.logger.info(f"🧠 CIO Nota {position.symbol}: Sugiere cautela ({ai_reason}), pero en zona neutral ({profit_pips:+.1f} pips).")
                            setattr(self, f"_last_log_time_{position.symbol}", now_ts)
                            
                elif decision == "HOLD" and profit_pips >= self.activation_pips:
                    # Si la IA dice que mantenga y YA pasó la barrera de activación, solo ponemos Break Even para dejarlo respirar
                    if position.sl < position.price_open and position.type == mt5.ORDER_TYPE_BUY:
                         new_sl = position.price_open # BREAK EVEN EXACTO
                         last_log_time = getattr(self, f"_last_log_time_{position.symbol}", 0)
                         if now_ts - last_log_time > 30:
                             self.logger.info(f"🧠 CIO RELAX en {position.symbol}: {ai_reason}. Fijando solo Break Even (Safe Zone).")
                             setattr(self, f"_last_log_time_{position.symbol}", now_ts)
                    elif position.sl > position.price_open and position.type == mt5.ORDER_TYPE_SELL:
                         new_sl = position.price_open # BREAK EVEN EXACTO
                         last_log_time = getattr(self, f"_last_log_time_{position.symbol}", 0)
                         if now_ts - last_log_time > 30:
                             self.logger.info(f"🧠 CIO RELAX en {position.symbol}: {ai_reason}. Fijando solo Break Even (Safe Zone).")
                             setattr(self, f"_last_log_time_{position.symbol}", now_ts)
                    else:
                         ai_approved = False # Ya estamos en B.E o mejor, dejamos respirar
                elif decision == "HOLD":
                    ai_approved = False

            # ─── EJECUTAR LA MODIFICACIÓN TÁCTICA ────────────────────
            if ai_approved:
                # Solo enviar a MT5 si el movimiento es al menos 1.0 pip (evita spam 10016 al broker)
                if position.type == mt5.ORDER_TYPE_BUY and new_sl > position.sl:
                    if (new_sl - position.sl) / pip_in_points >= 1.0:
                        self._modify_sl(position, new_sl, profit_pips)
                elif position.type == mt5.ORDER_TYPE_SELL and (position.sl == 0.0 or new_sl < position.sl):
                    if position.sl == 0.0 or (position.sl - new_sl) / pip_in_points >= 1.0:
                        self._modify_sl(position, new_sl, profit_pips)

    def _execute_partial_close(self, position, tick):
        """Cierra el 50% de la posición e intenta poner Breakeven"""
        if position.ticket in self.partial_closes_done:
            return
            
        close_volume = position.volume / 2.0
        symbol_info = mt5.symbol_info(position.symbol)
        lot_step = symbol_info.volume_step
        close_volume = round(close_volume / lot_step) * lot_step
        close_volume = round(close_volume, 2) # 🔴 FIX: Normalización de volumen estricta para MT5
        
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
        symbol_info = mt5.symbol_info(position.symbol)
        if not symbol_info:
            return
            
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": round(new_sl, symbol_info.digits), # 🔴 FIX: Flotantes de SL Normalizados
            "tp": round(position.tp, symbol_info.digits) if position.tp > 0 else 0.0, # Normalizar TP
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
