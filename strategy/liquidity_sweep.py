"""
📊 TX3 PRO - ESTRATEGIA: INSTITUTIONAL LIQUIDITY SWEEP (ILS)
==========================================================
Lógica: Identifica "falsos rompimientos" en los máximos/mínimos 
de las últimas 4 horas (Liquidity Sweeps) y busca una reversión 
rápida validada por Regresión Lineal (LSMA).
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime

class LiquiditySweepStrategy:
    def __init__(self, logger, symbol, timeframe=mt5.TIMEFRAME_M5):
        self.logger = logger
        self.symbol = symbol
        self.timeframe = timeframe
        
        # Parámetros Optimización
        self.lookback_hours = 4     # Rango de liquidez
        self.sweep_pips_min = 1.0   # Mínimo barrido para validar
        self.sweep_pips_max = 8.0   # Máximo barrido (si es más, es ruptura real)
        self.lsma_period = 25       # Suavizado de regresión lineal
        
    def get_name(self) -> str:
        return f"ILS_Sweep_{self.symbol}"

    def _calculate_lsma(self, series, period):
        """Calcula Least Squares Moving Average (LSMA)"""
        weights = np.arange(1, period + 1)
        return series.rolling(window=period).apply(
            lambda x: np.polyfit(weights, x, 1)[0] * period + np.polyfit(weights, x, 1)[1],
            raw=True
        )

    def generate_signal(self) -> dict | None:
        # 1. Obtener datos M5 para la entrada
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 100)
        if rates is None or len(rates) < 50: return None
        
        df = pd.DataFrame(rates)
        df['lsma'] = self._calculate_lsma(df['close'], self.lsma_period)
        
        # 2. Identificar niveles de Liquidez (H1 - últimas 4h)
        h1_rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 1, self.lookback_hours)
        if h1_rates is None: return None
        
        # Filtro de Tendencia Macro (EMA 200 en H1)
        h1_long = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 250)
        trend = "UNKNOWN"
        if h1_long is not None and len(h1_long) > 200:
            df_trend = pd.DataFrame(h1_long)
            df_trend['ema200'] = df_trend['close'].ewm(span=200, adjust=False).mean()
            trend = "BULL" if df_trend.iloc[-1]['close'] > df_trend.iloc[-1]['ema200'] else "BEAR"
        
        liq_high = max([r['high'] for r in h1_rates])
        liq_low = min([r['low'] for r in h1_rates])
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        pip = 0.0001 if "JPY" not in self.symbol else 0.01
        
        # --- LÓGICA DE DETECCIÓN DE SWEEP ---
        
        signal = None
        reason = ""
        
        # SELL Setup: El precio barrió el máximo y regresó
        if prev['high'] > liq_high and (prev['high'] - liq_high) < (self.sweep_pips_max * pip):
            if last['close'] < liq_high and last['close'] < last['lsma'] and trend == "BEAR":
                signal = "SELL"
                reason = f"Liquidity Sweep detected at {liq_high:.5f} (High) + Bear Trend"

        # BUY Setup: El precio barrió el mínimo y regresó
        elif prev['low'] < liq_low and (liq_low - prev['low']) < (self.sweep_pips_max * pip):
            if last['close'] > liq_low and last['close'] > last['lsma'] and trend == "BULL":
                signal = "BUY"
                reason = f"Liquidity Sweep detected at {liq_low:.5f} (Low) + Bull Trend"

        if signal:
            # Filtro adicional: Solo operar en sesiones de alta liquidez
            from zoneinfo import ZoneInfo
            hour_est = datetime.now(ZoneInfo("America/New_York")).hour
            if hour_est < 2 or hour_est >= 13: # Solo Londres y Mañana de NY
                return None

            # Calcular ATR para SL/TP dinámico
            df['tr'] = np.maximum(df['high'] - df['low'], 
                       np.maximum(abs(df['high'] - df['close'].shift()), 
                                 abs(df['low'] - df['close'].shift())))
            atr = df['tr'].rolling(14).mean().iloc[-1]
            
            return {
                "symbol": self.symbol,
                "signal": signal,
                "reason": reason,
                "stop_loss_pips": max(round(atr * 1.5 / pip / 10, 1), 10.0), # SL atrás de la mecha
                "take_profit_pips": max(round(atr * 3.0 / pip / 10, 1), 20.0), # R:R 1:2 preferido
                "strategy": "ILS_Sweep"
            }

        return None
