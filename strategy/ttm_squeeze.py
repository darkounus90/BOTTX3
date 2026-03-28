import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class TTMSqueezeStrategy(BaseStrategy):
    """
    🌪️ TTM Squeeze Pro (Volatility Breakout Hunter)
    ================================================
    Diseñada exclusivamente para operar la inyección de volumen masivo 
    de Londres y Nueva York (Sesiones Tendenciales).
    
    Lógica Cuantitativa:
    1. Detecta compresión de volatilidad (Bollinger Bands dentro de Keltner Channels).
    2. Espera la "explosión" (Bollinger rompe Keltner hacia afuera).
    3. Dispara en la dirección del Momentum institucional (Cruce rápido de EMA).
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        
        # Parámetros Institucionales
        self.length = 20
        self.bb_mult = 2.0
        self.kc_mult = 1.5
        self.bars_needed = 200
        self.last_processed_time = None

    def get_name(self) -> str:
        return f"TTM Squeeze ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        # --- CAZADOR DE TENDENCIAS (LONDRES Y NY) ---
        hour_est = datetime.now(ZoneInfo("America/New_York")).hour
        
        # Operamos Londres (3 a 7 EST) y la Mañana NY (8 a 12 EST)
        # Filtramos la zona muerta asiática porque el Squeeze fallaría
        if hour_est >= 13 or hour_est < 3:
            return None

        last_closed_time = rates[-2]['time']
        if self.last_processed_time == last_closed_time:
            return None
        self.last_processed_time = last_closed_time

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # ATR para Keltner
        tr = pd.concat([df['high'] - df['low'], 
                        abs(df['high'] - df['close'].shift()), 
                        abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
        df['atr'] = tr.rolling(self.length).mean()

        # Bollinger Bands (BB)
        df['sma_20'] = df['close'].rolling(self.length).mean()
        df['std_20'] = df['close'].rolling(self.length).std()
        df['bb_upper'] = df['sma_20'] + (df['std_20'] * self.bb_mult)
        df['bb_lower'] = df['sma_20'] - (df['std_20'] * self.bb_mult)

        # Keltner Channels (KC)
        df['ema_20'] = df['close'].ewm(span=self.length, adjust=False).mean()
        df['kc_upper'] = df['ema_20'] + (df['atr'] * self.kc_mult)
        df['kc_lower'] = df['ema_20'] - (df['atr'] * self.kc_mult)

        # Estado del Squeeze
        df['squeeze_on'] = (df['bb_upper'] < df['kc_upper']) & (df['bb_lower'] > df['kc_lower'])
        
        # Momentum (Dirección)
        df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
        df['ema_34'] = df['close'].ewm(span=34, adjust=False).mean()
        df['momentum_bull'] = df['ema_8'] > df['ema_34']
        df['momentum_bear'] = df['ema_8'] < df['ema_34']

        # H1 Macro Trend Filter
        h1_rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 200)
        is_uptrend_h1 = False
        is_downtrend_h1 = False
        if h1_rates is not None and len(h1_rates) > 100:
            df_h1 = pd.DataFrame(h1_rates)
            ema_200_h1 = df_h1['close'].ewm(span=200, adjust=False).mean()
            is_uptrend_h1 = df_h1['close'].iloc[-2] > ema_200_h1.iloc[-2]
            is_downtrend_h1 = df_h1['close'].iloc[-2] < ema_200_h1.iloc[-2]

        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        prev3 = df.iloc[-4]

        # Lógica Firing (Disparo) del Squeeze
        # Ocurre cuando estábamos en Squeeze (compresión) en la vela pasada, y en la vela 'prev' se rompe hacia afuera.
        was_squeezed = prev2['squeeze_on'] or prev3['squeeze_on']
        is_firing = not prev['squeeze_on']

        signal_type = None

        if was_squeezed and is_firing:
            if prev['momentum_bull'] and is_uptrend_h1 and prev['close'] > prev['kc_upper']:
                signal_type = "BUY"
            elif prev['momentum_bear'] and is_downtrend_h1 and prev['close'] < prev['kc_lower']:
                signal_type = "SELL"

        if not signal_type:
            return None

        # Gestión de Riesgo Expansiva (Para cazar tendencias grandes)
        pip_size = 0.01 if "JPY" in self.symbol else 0.0001
        atr_val = prev['atr']
        point = pip_size / 10

        # SL en la base de la ruptura (1.5 ATR), TP enorme (4.0 ATR) porque es tendencia
        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 4.0) / (10 * point), 1)
        
        sl_pips = max(sl_pips, 15.0)
        tp_pips = max(tp_pips, 30.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": f"TTM Squeeze Fired | Momentum Aligned | SL: {sl_pips}p TP: {tp_pips}p"
        }

        self.log_signal(ts_signal)
        return ts_signal
