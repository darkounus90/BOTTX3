import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class SydneyOpeningBreakoutStrategy(BaseStrategy):
    """
    🦘 Sydney Opening Range Breakout (Pacific Session)
    =================================================
    Estrategia de fuerza bruta cuantitativa que busca el verdadero
    desplazamiento del dinero inteligente en la apertura del mercado de Sídney.
    
    Lógica:
    1. Define el rango direccional justo después del cierre de New York.
    2. Espera a que abra Sydney (17:00 EST / 5:00 PM EST).
    3. Cuando una vela (M15) cierra decididamente fuera del rango establecido, 
       se entra a favor de la ruptura asumiendo que es el comienzo del ritmo del Pacífico.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15  # M15 es el estándar para atrapar breakouts sólidos sin ruido
        
        # Guardaremos el rango del día dinámicamente
        self.current_day = None
        self.range_high = None
        self.range_low = None
        self.range_calculated = False
        
        self.bars_needed = 40  # Necesitamos suficientes barras para mirar hacia atrás unas horas
        self.logger.info(f"✨ Estrategia Cargada: Sydney Opening Breakout ({self.symbol})")

    def get_name(self) -> str:
        return f"Sydney Breakout Institucional ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Vela anterior 100% cerrada (Nunca usar la que está en curso)
        last_closed = df.iloc[-2]
        
        # --- EVITAR SPAM EN LA MISMA VELA (Deduplicación) ---
        current_candle_time = last_closed['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
            
        server_now = current_candle_time  # Usamos la hora de la vela del server (usualmente GMT+2 o +3)
        current_day_str = server_now.strftime("%Y-%m-%d")

        # 1. RESET Y CÁLCULO DEL RANGO DIARIO
        if self.current_day != current_day_str:
            self.current_day = current_day_str
            self.range_high = None
            self.range_low = None
            self.range_calculated = False
            self.has_traded_today = False  # Solo 1 breakout válido por día

        # 1.5 CONTROL DE HORARIOS ESTRICTOS (Solo operar apertura Sydney)
        local_hour = datetime.now(ZoneInfo("America/New_York")).hour
        # Sydney abre a las 17:00 EST y la gran volatilidad suele durar un par de horas hasta que Tokio toma el relevo a las 19:00 EST.
        if local_hour < 17 or local_hour >= 19:
            return None # Si no estamos entre las 5:00 PM y las 7:00 PM EST, ignorar

        # Enfoque Cuantitativo Robusto:
        # Detectar el rango de consolidación Post-NY (últimas 16 velas = 4 horas)
        lookback_df = df.iloc[-18:-2] # Excluyendo la vela recién cerrada
        
        # Calcular el verdadero techo y piso de esas 4 horas
        current_range_high = lookback_df['high'].max()
        current_range_low = lookback_df['low'].min()
        rango_pips = (current_range_high - current_range_low) * 10000 # asumiendo que no es JPY

        # Si ya operó un breakout hoy y ganó, no re-entramos
        if getattr(self, 'has_traded_today', False):
            return None

        signal_type = None
        reason = ""

        # Lógica Fuerte de Ruptura (Momentum) 🚀
        # 1. El mercado estuvo metido en una caja (consolidation)
        # 2. La última vela CERRÓ agresivamente por encima/debajo de esa caja.
        # 3. La vela en sí misma debe ser grande, mostrando poder institucional (no mechas débiles).
        
        vela_size = abs(last_closed['close'] - last_closed['open']) * 10000
        
        # BREAKOUT ALCISTA (BUY)
        if last_closed['close'] > current_range_high and last_closed['open'] < current_range_high:
            if vela_size > 3.0: # La vela de ruptura debe tener cuerpo sustancial (>3 pips puros)
                signal_type = "BUY"
                reason = "Sydney Range Breakout Alcista (Momentum)"

        # BREAKOUT BAJISTA (SELL)
        elif last_closed['close'] < current_range_low and last_closed['open'] > current_range_low:
            if vela_size > 3.0:
                signal_type = "SELL"
                reason = "Sydney Range Breakout Bajista (Momentum)"

        if not signal_type:
            return None

        # Marcamos que ya disparamos esta vela
        self.last_signal_time = current_candle_time
        
        # Marcar que ya hubo ruptura hoy (para no spamear entradas si entra de nuevo a la caja y sale)
        self.has_traded_today = True

        # --- GESTIÓN DE RIESGO ---
        # Calculamos ATR de 14 periodos
        high_low = df['high'] - df['low']
        atr = high_low.rolling(14).mean().iloc[-2]
        
        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point if symbol_info else 0.00001
        
        sl_dist = atr * 1.5
        tp_dist = atr * 3.5
        
        sl_pips = round(sl_dist / (10 * point), 1)
        tp_pips = round(tp_dist / (10 * point), 1)
        
        sl_pips = max(sl_pips, BotConfig.DEFAULT_SL_PIPS)
        tp_pips = max(tp_pips, BotConfig.DEFAULT_TP_PIPS)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason,
            "adx": 30.0 
        }

        self.log_signal(ts_signal)
        return ts_signal
