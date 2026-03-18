import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
from zoneinfo import ZoneInfo

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class AsianScalperStrategy(BaseStrategy):
    """
    🌙 Asian Session Scalper (Prop Firm Safe)
    =========================================
    Opera en horas de bajísimo volumen (Asia/Pacific: 18:00 - 01:00 EST).
    Busca canales horizontales sin tendencia (ADX bajito) y compra el piso 
    o vende el techo.
    Métricas: Win Rate altísimo (>75%), TP de 5-8 pips, SL de 20-25 pips 
    (para sobrevivir el spread variable o mechazos huérfanos nocturnos).
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M5
        self.bars_needed = 40
        
        self.band_period = 20
        self.band_dev = 2.0
        self.rsi_period = 7       # RSI muy rápido para atrapar scalps
        self.rsi_ob = 75.0
        self.rsi_os = 25.0
        self.max_adx = 25.0       # Estricto: el mercado debe estar MUERTO (lateral)

    def get_name(self) -> str:
        return f"Asian Scalper ({self.symbol})"

    def _calculate_adx(self, df):
        # Simplified ADX logic for live bot
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr1 = pd.DataFrame(high - low)
        tr2 = pd.DataFrame(abs(high - close.shift(1)))
        tr3 = pd.DataFrame(abs(low - close.shift(1)))
        frames = [tr1, tr2, tr3]
        tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
        atr = tr.rolling(self.adx_period).mean()
        
        plus_di = 100 * (plus_dm.ewm(alpha=1/self.adx_period).mean() / atr)
        minus_di = abs(100 * (minus_dm.ewm(alpha=1/self.adx_period).mean() / atr))
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        adx = ((dx.shift(1) * (self.adx_period - 1)) + dx) / self.adx_period
        adx.smooth = dx.ewm(alpha=1/self.adx_period).mean()
        return adx.smooth

    def generate_signal(self) -> dict | None:
        hour_est = datetime.now(ZoneInfo("America/New_York")).hour
        
        # Filtro Horario: Solo de 18:00 PM a 01:00 AM EST (Tokio/Sydney muertos)
        if not (hour_est >= 18 or hour_est <= 1):
            return None

        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # Calcular Indicadores (RSI, Bollinger, ADX)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        df['mavg'] = df['close'].rolling(window=self.band_period).mean()
        df['std'] = df['close'].rolling(window=self.band_period).std()
        df['bb_upper'] = df['mavg'] + (self.band_dev * df['std'])
        df['bb_lower'] = df['mavg'] - (self.band_dev * df['std'])
        
        df['adx'] = self._calculate_adx(df)
        
        last = df.iloc[-2]  # Última vela M5 cerrada completamente

        if pd.isna(last['adx']) or pd.isna(last['rsi']):
            return None

        # Condición 1: Mercado 100% lateral (ADX M5 bajo)
        if last['adx'] > self.max_adx:
            return None

        signal_type = None
        reason = ""

        # Lógica Scalper Fader
        if last['close'] < last['bb_lower'] and last['rsi'] < self.rsi_os:
            signal_type = "BUY"
            reason = f"Asian Floor Scalp | ADX:{last['adx']:.1f} RSI:{last['rsi']:.1f}"
            
        elif last['close'] > last['bb_upper'] and last['rsi'] > self.rsi_ob:
            signal_type = "SELL"
            reason = f"Asian Ceiling Scalp | ADX:{last['adx']:.1f} RSI:{last['rsi']:.1f}"

        if not signal_type:
            return None

        # Evitar señales dobles en misma vela
        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        # Ratio Riesgo-Beneficio "Reverse" para win-rates altísimos
        sl_pips = 20.0
        tp_pips = 5.0 # Recogemos ganancias casi inmediatamente al revertir a la media

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
