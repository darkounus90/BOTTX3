import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class BollingerRSIStrategy(BaseStrategy):
    """
    🎯 Estrategia Institucional de Reversión a la Media
    =================================================
    Busca falsos rompimientos (manipulaciones) de rangos.
    Entra cuando el precio sale de la Banda de Bollinger (20, 2)
    y se apoya en un RSI extremo (periodo 14).
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M5 # M5 para entradas más rápidas como definiste
        self.bb_period = 20
        self.bb_dev = 1.8          # Reducido de 2.0 a 1.8 para tocar la banda más seguido
        self.rsi_period = 14
        self.rsi_overbought = 65.0 # Aflojado (antes 75) para que el RSI logre dar el "OK"
        self.rsi_oversold = 35.0   # Aflojado (antes 25) 
        self.adx_period = 14
        self.adx_threshold = 45.0  # Ampliado (antes 28): permite operar en mercados con más inercia
        self.bars_needed = 100

    def get_name(self) -> str:
        return f"Bollinger+RSI Reversion ({self.symbol})"

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula las Bandas de Bollinger, RSI y ADX/ATR"""
        
        # --- RSI (Relative Strength Index) ---
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))

        # --- Bollinger Bands ---
        df['sma_20'] = df['close'].rolling(window=self.bb_period).mean()
        df['std_20'] = df['close'].rolling(window=self.bb_period).std()
        
        df['bb_upper'] = df['sma_20'] + (df['std_20'] * self.bb_dev)
        df['bb_lower'] = df['sma_20'] - (df['std_20'] * self.bb_dev)

        # --- ATR (Average True Range) para Stop Loss dinámico ---
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = df[['high', 'low', 'close']].copy()
        tr['tr'] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr['tr'].rolling(window=14).mean()

        # --- ADX Simple (Approximation) ---
        up_move = df['high'] - df['high'].shift(1)
        down_move = df['low'].shift(1) - df['low']
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        
        plus_dm_series = pd.Series(plus_dm, index=df.index)
        minus_dm_series = pd.Series(minus_dm, index=df.index)
        
        # Smoothed True Range and DM
        atr_adx = tr['tr'].ewm(alpha=1/self.adx_period, adjust=False).mean()
        plus_di = 100 * (plus_dm_series.ewm(alpha=1/self.adx_period, adjust=False).mean() / atr_adx)
        minus_di = 100 * (minus_dm_series.ewm(alpha=1/self.adx_period, adjust=False).mean() / atr_adx)
        
        dx = 100 * (np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
        df['adx'] = dx.ewm(alpha=1/self.adx_period, adjust=False).mean()

        return df

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        df = self._calculate_indicators(df)
        
        # Evaluamos el cierre de la ÚLTIMA vela completada (iloc[-2])
        # Para evitar repintado, nunca tomamos la vela en curso (iloc[-1])
        last_closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        
        # Evitamos operar si la tendencia es tan agresiva que romperá bandas sin piedad
        if last_closed['adx'] > self.adx_threshold:
            self.logger.debug(f"{self.symbol} ADX alto ({last_closed['adx']:.1f} > {self.adx_threshold}). Evitando operar contra tendencia.")
            return None

        # --- FILTRO DE SPREAD ---
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return None
        
        spread_pips = symbol_info.spread * (10 if symbol_info.digits == 3 or symbol_info.digits == 5 else 1) / 10.0 # Ajuste pips
        if spread_pips > getattr(BotConfig, "MAX_SPREAD_PIPS", 3.0):
            self.logger.debug(f"{self.symbol} Spread alto ({spread_pips:.1f} pips). Ignorando señal.")
            return None

        signal_type = None
        reason = ""
        
        # LÓGICA DE EVENTOS PRINCIPAL

        # ---------------- BUY (Largo) ---------------- 
        # Criterios: 
        # 1. El precio toca/rompe por debajo la banda inferior de Bollinger.
        # 2. RSI está en zona de sobreventa (<= 30).
        # 3. Pequeño filtro de pivote: La vela anterior estuvo por debajo de Bollinger, pero cerró mejorando un poco 
        #    (o al menos demostrando rechazo). O la actual cruza cerrando hacia arriba.
        is_oversold = last_closed['rsi'] <= self.rsi_oversold
        broke_lower_band = last_closed['close'] <= last_closed['bb_lower'] or last_closed['low'] <= last_closed['bb_lower']
        
        # ---------------- SELL (Corto) ---------------- 
        # Criterios: 
        # 1. El precio toca/rompe por arriba la banda superior de Bollinger.
        # 2. RSI está en zona de sobrecompra (>= 70).
        is_overbought = last_closed['rsi'] >= self.rsi_overbought
        broke_upper_band = last_closed['close'] >= last_closed['bb_upper'] or last_closed['high'] >= last_closed['bb_upper']

        
        # ---------------- GATILLO CON RECHAZO (Wick Rejection) ---------------- 
        # No basta con tocar la banda, queremos ver que el precio fue RECHAZADO (Mecha larga)
        lower_wick = last_closed['open'] - last_closed['low'] if last_closed['open'] < last_closed['close'] else last_closed['close'] - last_closed['low']
        upper_wick = last_closed['high'] - last_closed['close'] if last_closed['open'] < last_closed['close'] else last_closed['high'] - last_closed['open']
        cuerpo = abs(last_closed['close'] - last_closed['open'])
        
        # BUY (Largo): Rechazo en zona de sobreventa
        if is_oversold and broke_lower_band:
            if lower_wick > (cuerpo * 0.8): # La mecha inferior debe ser casi tan grande como el cuerpo (Rechazo)
                signal_type = "BUY"
                reason = f"Institutional Rejection (Bottom) | RSI:{last_closed['rsi']:.1f}"
            
        # SELL (Corto): Rechazo en zona de sobrecompra
        elif is_overbought and broke_upper_band:
            if upper_wick > (cuerpo * 0.8):
                signal_type = "SELL"
                reason = f"Institutional Rejection (Top) | RSI:{last_closed['rsi']:.1f}"
            
        if not signal_type:
            return None

        # --- EVITAR SPAM EN LA MISMA VELA (Deduplicación) ---
        current_candle_time = last_closed['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        # --- GESTIÓN DE RIESGO DINÁMICA ---
        point = symbol_info.point if symbol_info.point else 0.00001
        
        # Multiplicador ATR (1.5x ATR para Stop Loss ajustado, 2.0x ATR para Take Profit)
        sl_pip_dist = (last_closed['atr'] * 1.5) / (point * 10)
        tp_pip_dist = (last_closed['atr'] * 2.0) / (point * 10)

        # Forzamos mínimos pero más bajos (Sniper Mode: 8 pips SL / 15 pips TP mín para cubrir comisiones)
        sl_pips = max(round(sl_pip_dist, 1), 8.0)
        tp_pips = max(round(tp_pip_dist, 1), 15.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "adx": last_closed['adx'], # Guardamos ADX para que SMC o el Oráculo tengan contexto
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
