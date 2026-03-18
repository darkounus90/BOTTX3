import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class FractalEnergyStrategy(BaseStrategy):
    """
    ⚡ Fractal Energy Exhaustion
    ================================================
    Estrategia de patente privada (No-Internet).
    Mide la "Eficiencia Física" de los movimientos del mercado.
    Si el mercado se mueve direccionalmente con >60% de eficiencia 
    (cuerpos de velas enormes sin mechas) y entra en sobre-impulso (RSI), 
    es una burbuja algorítmica.
    Buscamos un "Engulfing" (Vela Envolvente) como detonador para atrapar 
    la reversión explosiva. 
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15 # Óptimo en M15
        self.efficiency_period = 10
        self.efficiency_threshold = 0.60
        self.rsi_period = 7
        self.bars_needed = 200

    def get_name(self) -> str:
        return f"Fractal Energy Exhaustion ({self.symbol})"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # 1. Calcular Energía Fractal (Eficiencia del Precio)
        df['body_size'] = abs(df['close'] - df['open'])
        df['full_size'] = abs(df['high'] - df['low'])
        
        df['sum_body'] = df['body_size'].rolling(self.efficiency_period).sum()
        df['sum_full'] = df['full_size'].rolling(self.efficiency_period).sum()
        df['efficiency'] = df['sum_body'] / (df['sum_full'] + 1e-9)

        # 2. RSI rápido para detectar impulsos insostenibles
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi_7'] = 100 - (100 / (1 + rs))

        # 3. ATR Dinámico
        df['atr'] = df['full_size'].rolling(14).mean()

        prev = df.iloc[-3]
        last = df.iloc[-2]

        signal_type = None
        reason = ""

        # Lógica de Explosión (Burbuja Fractal)
        if prev['efficiency'] > self.efficiency_threshold:
            
            # Buscando Techo (Venta)
            if prev['rsi_7'] > 80:
                is_engulfing_bear = last['close'] < last['open'] and last['open'] >= prev['close'] and last['close'] < prev['open']
                if is_engulfing_bear:
                    signal_type = "SELL"
                    reason = "Burbuja Fractal (>60% ef, RSI>80) + Bearish Engulfing"
                    
            # Buscando Suelo (Compra)
            elif prev['rsi_7'] < 20:
                is_engulfing_bull = last['close'] > last['open'] and last['open'] <= prev['close'] and last['close'] > prev['open']
                if is_engulfing_bull:
                    signal_type = "BUY"
                    reason = "Colapso Fractal (>60% ef, RSI<20) + Bullish Engulfing"

        if not signal_type:
            return None

        current_candle_time = last['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        pip_size = 0.01 if "JPY" in self.symbol else 0.0001
        atr_val = last['atr']
        point = pip_size / 10

        # Parámetros institucionales: SL ancho, TP masivo (R:R estricto)
        sl_pips = round((atr_val * 2.0) / (10 * point), 1)
        tp_pips = round((atr_val * 3.0) / (10 * point), 1) 
        sl_pips = max(sl_pips, 15.0)
        tp_pips = max(tp_pips, 22.5)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
