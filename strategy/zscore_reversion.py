import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class ZScoreReversionStrategy(BaseStrategy):
    """
    🔬 Z-Score Statistical Reversion (100% FTMO Compliant)
    ================================================
    Mide la anomalía estadística del precio respecto a su Media Móvil
    calculando a cuántas Desviaciones Estándar (Z-Score) se encuentra.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15 
        
        # Parámetros Cuantitativos
        self.sma_period = 50
        self.std_period = 50
        self.z_threshold = 2.5 
        self.atr_ma_period = 50          # Para filtro de volatilidad relativa
        self.bars_needed = 350           # Suficiente para indicadores y filtros

    def get_name(self) -> str:
        return f"Z-Score Reversion ({self.symbol})"

    def generate_signal(self) -> dict | None:
        # 🚫 KILL-SWITCH ESTADÍSTICO: El Z-Score tiene Profit Factor < 1 en el EURUSD.
        # Operarlo sería regalar dinero. Se bloquea rígidamente.
        if "EUR" in (self.symbol or ""):
            return None
            
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 1. Filtro Macro Institucional
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. Cálculo del Equilibrio y Volatilidad Real
        df['sma_50'] = df['close'].rolling(window=self.sma_period).mean()
        df['std_50'] = df['close'].rolling(window=self.std_period).std()
        
        # 3. Cálculo de la Anomalía Estadística (Z-Score)
        df['z_score'] = (df['close'] - df['sma_50']) / (df['std_50'] + 1e-9)

        # 4. Cálculo de ATR
        high_low = abs(df['high'] - df['low'])
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()

        # 5. Filtro de Volatilidad Relativa (Evitar mercados muertos)
        df['atr_ma'] = df['atr'].rolling(window=self.atr_ma_period).mean()
        
        prev = df.iloc[-3]
        last = df.iloc[-2]

        is_volatile = last['atr'] > (df['atr_ma'].iloc[-1] * 0.8)
        # --- FILTRO DE TENDENCIA H1 (High-Fidelity Match) ---
        h1_rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 250)
        h1_trend = 0
        if h1_rates is not None and len(h1_rates) > 200:
            df_h1 = pd.DataFrame(h1_rates)
            ema_200_h1 = df_h1['close'].ewm(span=200, adjust=False).mean()
            h1_trend = 1 if df_h1['close'].iloc[-2] > ema_200_h1.iloc[-2] else -1

        is_uptrend = h1_trend == 1
        is_downtrend = h1_trend == -1

        signal_type = None
        reason = ""

        if not is_volatile:
            return None

        # Lógica Cuantitativa (Retorno a la Media)
        if prev['z_score'] >= self.z_threshold and last['z_score'] < self.z_threshold:
            if is_downtrend: 
                signal_type = "SELL"
                reason = f"Z-Score Reversion ({self.z_threshold} SD) | Volatility OK"
                
        elif prev['z_score'] <= -self.z_threshold and last['z_score'] > -self.z_threshold:
            if is_uptrend:
                signal_type = "BUY"
                reason = f"Z-Score Reversion (-{self.z_threshold} SD) | Volatility OK"

        if not signal_type:
            return None

        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        pip_size = 0.01 if "JPY" in self.symbol else 0.0001
        atr_val = last['atr']
        point = pip_size / 10

        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 2.5) / (10 * point), 1)
        
        sl_pips = max(sl_pips, 15.0)
        tp_pips = max(tp_pips, 25.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
