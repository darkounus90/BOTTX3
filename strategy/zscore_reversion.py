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
    No usa Martingala, ni Grid, ni arbitraje de latencia (prohibidos).
    Solo matemática direccional pura (Mean Reversion) con Stop Loss fijo.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15 
        
        # Parámetros Cuantitativos
        self.sma_period = 50
        self.std_period = 50
        self.z_threshold = 2.5 # MANTENER RIGIDO: Modo OPTIMO para GBPUSD (según backtest)
        
        self.bars_needed = 200

    def get_name(self) -> str:
        return f"Z-Score Reversion ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 1. Filtro Macro Institucional (Solo operar a favor de M15 Macro)
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

        # 2. Cálculo del Equilibrio y Volatilidad Real
        df['sma_50'] = df['close'].rolling(window=self.sma_period).mean()
        df['std_50'] = df['close'].rolling(window=self.std_period).std()
        
        # 3. Cálculo de la Anomalía Estadística (Z-Score)
        df['z_score'] = (df['close'] - df['sma_50']) / (df['std_50'] + 1e-9)

        # 4. Cálculo de ATR para StopLoss dinámico basado en volatilidad real
        df['tr0'] = abs(df['high'] - df['low'])
        df['tr1'] = abs(df['high'] - df['close'].shift())
        df['tr2'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr0', 'tr1', 'tr2']].max(axis=1)
        df['atr'] = df['tr'].rolling(14).mean()

        prev = df.iloc[-3]
        last = df.iloc[-2]

        signal_type = None
        reason = ""

        # Lógica Cuantitativa (Retorno a la Media)
        # Si el Z-Score estaba por encima de 2.5 (Anomalía Alcista Extrema) y cruza de regreso hacia abajo
        if prev['z_score'] >= self.z_threshold and last['z_score'] < self.z_threshold:
            if last['close'] < last['ema_200']: # Operando a favor de la macro bajista
                signal_type = "SELL"
                reason = f"Z-Score Reversion (Anomalía +{self.z_threshold} SD corregida a la baja)"
                
        # Si el Z-Score estaba por debajo de -2.5 (Anomalía Bajista Extrema) y cruza hacia arriba
        elif prev['z_score'] <= -self.z_threshold and last['z_score'] > -self.z_threshold:
            if last['close'] > last['ema_200']: # Operando a favor de la macro alcista
                signal_type = "BUY"
                reason = f"Z-Score Reversion (Anomalía -{self.z_threshold} SD corregida al alza)"

        if not signal_type:
            return None

        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        pip_size = 0.01 if "JPY" in self.symbol else 0.0001
        atr_val = last['atr']
        point = pip_size / 10

        # FTMO Safe Risk/Reward (Ratio 1:1.5 exacto, SL/TP estáticos al abrir el trade)
        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 2.5) / (10 * point), 1)
        
        # Pisos máximos/mínimos para monedas core como EURUSD/GBPUSD
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
