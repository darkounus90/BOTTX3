"""
🏗️ TX3 PRO - ESTRATEGIA: GOLDEN ZONE REVERSION (EURUSD SPECIALIST)
===================================================================
Lógica: Detecta impulsos institucionales y espera el retroceso a la 
'Zona Dorada' (FiIbonacci 61.8%) para entrar a favor de la tendencia.
Optimizado para EURUSD debido a su naturaleza de reversión porcentual.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime

class GoldenZoneStrategy:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M5):
        self.symbol = symbol
        self.timeframe = timeframe
        self.logger = logging.getLogger("GoldenZone")
        
        # Parámetros Golden
        self.impulse_period = 36 # ~3 horas en M5
        self.min_impulse_pips = 15.0
        self.fib_level = 0.618 
        self.fib_tolerance = 0.05 # 5% de tolerancia alrededor del nivel
        
    def get_name(self) -> str:
        return f"GZR_GOLDEN_{self.symbol}"

    def generate_signal(self) -> dict | None:
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 100)
        if rates is None or len(rates) < 100: return None
        df = pd.DataFrame(rates)
        
        # 1. Identificar el impulso más reciente (High/Low del periodo de lookback)
        window = df.iloc[-self.impulse_period:]
        highest = window['high'].max()
        lowest = window['low'].min()
        
        pip = 0.0001 if "JPY" not in self.symbol else 0.01
        impulse_pips = (highest - lowest) / (10 * pip)
        
        if impulse_pips < self.min_impulse_pips:
            return None
            
        # Determinar dirección del impulso (dónde está el precio respecto al High/Low)
        curr_price = df.iloc[-1]['close']
        
        signal = None
        target_entry = 0
        
        # --- LÓGICA BULLISH (Retroceso tras impulso alcista) ---
        # Si el High ocurrió después que el Low, es tendencia alcista.
        high_idx = window['high'].idxmax()
        low_idx = window['low'].idxmin()
        
        if high_idx > low_idx:
            # Entrada en el 61.8% de Fibonacci del impulso
            target_entry = highest - (highest - lowest) * self.fib_level
            # Si el precio actual está muy cerca de la Golden Zone (+- tolerancia)
            if abs(curr_price - target_entry) < (2.0 * pip):
                # Filtro: Necesitamos una vela de confirmación (M5 cerrando por encima de la zona)
                if curr_price > df.iloc[-2]['close'] and curr_price > df.iloc[-1]['open']:
                    signal = "BUY"
                    
        # --- LÓGICA BEARISH (Retroceso tras impulso bajista) ---
        elif low_idx > high_idx:
            target_entry = lowest + (highest - lowest) * self.fib_level
            if abs(curr_price - target_entry) < (2.0 * pip):
                if curr_price < df.iloc[-2]['close'] and curr_price < df.iloc[-1]['open']:
                    signal = "SELL"

        if signal:
            # ATR para Stops
            tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            
            # SL por debajo/encima del inicio del impulso o 1.5 ATR
            sl_pips = max(round(atr * 1.5 / pip / 10, 1), 12.0)
            tp_pips = max(round(atr * 3.0 / pip / 10, 1), 24.0)
            
            return {
                "symbol": self.symbol,
                "type": signal,
                "reason": f"EURUSD Golden Zone Reversion (Fib {self.fib_level*100}%)",
                "sl_pips": sl_pips,
                "tp_pips": tp_pips,
                "strategy": "GZR_GOLDEN_V1"
            }

        return None
