import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger
from datetime import datetime
from zoneinfo import ZoneInfo

class SqueezeMomentumStrategy(BaseStrategy):
    """
    🌪️ Volatility Squeeze Momentum (John Carter's Squeeze)
    ======================================================
    Combina Bandas de Bollinger y Canales Keltner para detectar
    "Squeezes" (Compresiones extremas de volatilidad).
    Cuando la volatilidad explota (Bollinger sale de Keltner),
    dispara a favor del Momentum (MACD o Regresión).
    Es la estrategia de tendencia definitiva para esquivar falsos rompimientos.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15  # El Squeeze es mortal en M15
        self.bars_needed = 100
        
        self.length = 20
        self.bb_mult = 2.0
        self.kc_mult = 1.5

    def get_name(self) -> str:
        return f"Squeeze Momentum M15 ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 1. Bollinger Bands
        df['basis'] = df['close'].rolling(self.length).mean()
        df['dev'] = self.bb_mult * df['close'].rolling(self.length).std()
        df['upperBB'] = df['basis'] + df['dev']
        df['lowerBB'] = df['basis'] - df['dev']

        # 2. Keltner Channels
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['range_ma'] = df['tr'].rolling(self.length).mean()
        df['upperKC'] = df['basis'] + df['range_ma'] * self.kc_mult
        df['lowerKC'] = df['basis'] - df['range_ma'] * self.kc_mult

        # 3. Squeeze Conditions
        # Squeeze On: BB is completely inside KC
        df['squeeze_on'] = (df['lowerBB'] > df['lowerKC']) & (df['upperBB'] < df['upperKC'])
        # Squeeze Off: BB expands outside KC
        df['squeeze_off'] = (df['lowerBB'] < df['lowerKC']) | (df['upperBB'] > df['upperKC'])

        # 4. Momentum (Simple MACD proxy para dirección)
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']

        # Evaluar la última y penúltima vela cerrada
        prev = df.iloc[-3]
        last = df.iloc[-2]

        # Trigger: Acabamos de salir del Squeeze (Explosión de Volatilidad)
        just_fired = prev['squeeze_on'] and last['squeeze_off']

        if not just_fired:
            return None

        signal_type = None
        reason = ""

        if last['macd'] > 0:
            signal_type = "BUY"
            reason = f"Bullish Squeeze Fire"
        elif last['macd'] < 0:
            signal_type = "SELL"
            reason = f"Bearish Squeeze Fire"

        if not signal_type:
            return None

        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        sl_pips = 15.0 # Stop Loss moderado
        tp_pips = 45.0 # Buscamos una corrida de momentum de 1:3

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
