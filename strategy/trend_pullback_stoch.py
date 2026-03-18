import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class TrendPullbackStochStrategy(BaseStrategy):
    """
    📈 Trend Pullback (StochRSI + EMA 200)
    ================================================
    La estrategia perfecta para Forex tendencial.
    1. Define tendencia Macro: El precio debe estar sobre la EMA 200.
    2. Espera un "Pullback": El StochRSI debe caer a sobreventa (<20).
    3. Gatillo: El StochRSI cruza hacia arriba, indicando que terminó 
       el retroceso y la tendencia retoma su camino.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15 # M15 para limpiar ruido
        self.ema_period = 200
        self.k_period = 3
        self.d_period = 3
        self.stoch_length = 14
        self.rsi_length = 14
        self.bars_needed = 300

    def get_name(self) -> str:
        return f"Trend Pullback Stoch ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # EMA 200 Macro
        df['ema_200'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # Cálculos de RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=self.rsi_length).mean()
        avg_loss = loss.rolling(window=self.rsi_length).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))

        # Cálculos de StochRSI
        rsi_min = df['rsi'].rolling(window=self.stoch_length).min()
        rsi_max = df['rsi'].rolling(window=self.stoch_length).max()
        df['stoch_k'] = 100 * ((df['rsi'] - rsi_min) / (rsi_max - rsi_min + 1e-9))
        df['stoch_k'] = df['stoch_k'].rolling(window=self.k_period).mean()
        df['stoch_d'] = df['stoch_k'].rolling(window=self.d_period).mean()

        # ATR para SL/TP dinámicos
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        prev = df.iloc[-3]
        last = df.iloc[-2]

        signal_type = None
        reason = ""

        # Lógica BULLISH (Tendencia Alcista)
        if last['close'] > last['ema_200']:
            # El K cruza al D hacia arriba, viniendo desde la sobreventa (<20)
            if prev['stoch_k'] <= prev['stoch_d'] and last['stoch_k'] > last['stoch_d'] and last['stoch_d'] < 25:
                signal_type = "BUY"
                reason = "Pullback completado en Tendencia Alcista"

        # Lógica BEARISH (Tendencia Bajista)
        elif last['close'] < last['ema_200']:
            # El K cruza al D hacia abajo, viniendo desde la sobrecompra (>80)
            if prev['stoch_k'] >= prev['stoch_d'] and last['stoch_k'] < last['stoch_d'] and last['stoch_d'] > 75:
                signal_type = "SELL"
                reason = "Pullback completado en Tendencia Bajista"

        if not signal_type:
            return None

        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        pip_size = 0.01 if "JPY" in self.symbol else 0.0001
        atr_val = last['atr']
        point = pip_size / 10

        # Parámetros institucionales: SL = 1.5 ATR, TP = 2.0 ATR
        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 2.0) / (10 * point), 1)
        sl_pips = max(sl_pips, 15.0)
        tp_pips = max(tp_pips, 30.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
