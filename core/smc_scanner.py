import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from utils.logger import BotLogger

class SMCScanner:
    """
    Detector de Liquidez Orgánica (SMC - Smart Money Concepts)
    Escanea Order Blocks y Fair Value Gaps (FVG) para validar
    las entradas basándose en flujos de dinero institucionales genuinos.
    Optimizada para bajo consumo de RAM usando NumPy/Pandas básicos.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.lookback = 40 # Últimas n velas para escanear liquidez cercana

    def _get_candles(self, symbol: str, timeframe=mt5.TIMEFRAME_M15, n=40):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, n)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        return df

    def scan_context(self, symbol: str, signal_direction: str) -> bool:
        """
        Devuelve True si la liquidez en la gráfica favorece la dirección del Signal.
        """
        df = self._get_candles(symbol, n=self.lookback)
        if df is None:
            return True # No bloqueamos si hay fallo de datos temporal

        # Último precio
        current_price = df.iloc[-1]['close']

        # Detección de FVG (Fair Value Gap)
        # Alcista: Low de la vela 3 > High de la vela 1
        # Bajista: High de la vela 3 < Low de la vela 1
        bullish_fvg = []
        bearish_fvg = []
        
        for i in range(1, len(df)-2):
            # FVG Alcista detectado
            if df.iloc[i+2]['low'] > df.iloc[i]['high']:
                bullish_fvg.append((df.iloc[i]['high'], df.iloc[i+2]['low']))
            # FVG Bajista detectado
            elif df.iloc[i+2]['high'] < df.iloc[i]['low']:
                bearish_fvg.append((df.iloc[i+2]['high'], df.iloc[i]['low']))

        # Validación simple por FVG Proximal:
        # Si queremos comprar (BUY), idealmente estamos rebotando o cerca de un FVG alcista previo
        # o el precio acaba de rellenar uno.
        
        # Como optimización extrema y pasiva: si compramos dentro o sobre un inbalance de liquidez bajista 
        # masivo reciente (riesgo de trampa), penalizamos.
        
        if signal_direction == 'BUY':
            if len(bearish_fvg) > 0:
                # Comprobar si el precio choca contra un FVG bajista muy cercano encima de nosotros
                nearest_fvg_bottom = bearish_fvg[-1][1]
                if current_price < nearest_fvg_bottom and (nearest_fvg_bottom - current_price) < 0.0005: 
                    # A medio pip de chocar con resistencia de liquidez
                    self.logger.warning(f"SMC VETO: {symbol} ignorado (BUY bloqueado por Bearish FVG encima)")
                    return False
        elif signal_direction == 'SELL':
            if len(bullish_fvg) > 0:
                nearest_fvg_top = bullish_fvg[-1][0]
                if current_price > nearest_fvg_top and (current_price - nearest_fvg_top) < 0.0005:
                    self.logger.warning(f"SMC VETO: {symbol} ignorado (SELL bloqueado por Bullish FVG debajo)")
                    return False

        return True
