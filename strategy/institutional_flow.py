"""
🏗️ TX3 PRO - ESTRATEGIA: INSTITUTIONAL FLOW (SMC 2.0)
======================================================
Lógica: Detecta Fair Value Gaps (FVG) en M15 (desequilibrios)
y espera un retroceso a la zona de mitigación (50%) validado
por un Market Structure Shift (MSS) en M5.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime

class InstitutionalFlowStrategy:
    def __init__(self, symbol, timeframe=mt5.TIMEFRAME_M5, logger=None):
        self.symbol = symbol
        self.entry_tf = timeframe
        self.context_tf = mt5.TIMEFRAME_M15
        self.logger = logger or logging.getLogger("InstitutionalFlow")
        
        # Parámetros SMC
        self.fvg_lookback = 50 
        self.mitigation_pct = 0.5 # Queremos al menos 50% de relleno del GAP
        
    def get_name(self) -> str:
        return f"IFS_SMC_{self.symbol}"

    def _find_fvgs(self, df):
        """Identifica FVGs activos y devuelve el más reciente e importante"""
        fvgs = []
        for i in range(1, len(df)-2):
            # FVG Alcista (Gap entre el High de la vela i y el Low de la vela i+2)
            if df.iloc[i+2]['low'] > df.iloc[i]['high']:
                fvgs.append({
                    'type': 'BULLISH',
                    'top': df.iloc[i+2]['low'],
                    'bottom': df.iloc[i]['high'],
                    'mid': (df.iloc[i+2]['low'] + df.iloc[i]['high']) / 2,
                    'is_mitigated': False
                })
            # FVG Bajista
            elif df.iloc[i+2]['high'] < df.iloc[i]['low']:
                fvgs.append({
                    'type': 'BEARISH',
                    'top': df.iloc[i]['low'],
                    'bottom': df.iloc[i+2]['high'],
                    'mid': (df.iloc[i]['low'] + df.iloc[i+2]['high']) / 2,
                    'is_mitigated': False
                })
        return fvgs

    def generate_signal(self) -> dict | None:
        # 1. Obtener Contexto M15
        rates_ctx = mt5.copy_rates_from_pos(self.symbol, self.context_tf, 0, self.fvg_lookback)
        if rates_ctx is None: return None
        df_ctx = pd.DataFrame(rates_ctx)
        
        fvgs = self._find_fvgs(df_ctx)
        if not fvgs: return None
        
        # 2. Obtener Precio Actual M5
        rates_entry = mt5.copy_rates_from_pos(self.symbol, self.entry_tf, 0, 50)
        if rates_entry is None: return None
        df_entry = pd.DataFrame(rates_entry)
        
        curr = df_entry.iloc[-1]
        prev = df_entry.iloc[-2]
        
        # 3. Lógica de Mitigación
        # Buscamos el último FVG no mitigado
        last_fvg = fvgs[-1] 
        
        signal = None
        reason = ""
        
        # --- CASO COMPRA (Mitigación de FVG Alcista) ---
        if last_fvg['type'] == 'BULLISH':
            # El precio debe haber entrado en la zona de mitigación (debajo del mid o top)
            if curr['close'] < last_fvg['top'] and curr['close'] > last_fvg['bottom']:
                # Market Structure Shift (M5): El precio empieza a subir de nuevo
                if curr['close'] > prev['high'] and curr['close'] > df_entry['close'].rolling(10).mean().iloc[-1]:
                    signal = "BUY"
                    reason = f"Mitigating Bullish FVG at {last_fvg['mid']:.5f} + MSS M5"

        # --- CASO VENTA (Mitigación de FVG Bajista) ---
        elif last_fvg['type'] == 'BEARISH':
            # El precio debe haber subido a la zona de mitigación
            if curr['close'] > last_fvg['bottom'] and curr['close'] < last_fvg['top']:
                # Market Structure Shift (M5): El precio rompe el mínimo anterior
                if curr['close'] < prev['low'] and curr['close'] < df_entry['close'].rolling(10).mean().iloc[-1]:
                    signal = "SELL"
                    reason = f"Mitigating Bearish FVG at {last_fvg['mid']:.5f} + MSS M5"

        if signal:
            # Calcular ATR para stops técnicos
            tr = pd.concat([df_entry['high'] - df_entry['low'], 
                           (df_entry['high'] - df_entry['close'].shift()).abs(), 
                           (df_entry['low'] - df_entry['close'].shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            pip = 0.0001 if "JPY" not in self.symbol else 0.01

            return {
                "symbol": self.symbol,
                "type": signal,
                "reason": reason,
                "sl_pips": max(round(atr * 1.2 / pip / 10, 1), 10.0), # SL más ajustado por ser SMC
                "tp_pips": max(round(atr * 3.5 / pip / 10, 1), 30.0), # Target estirado 1:3+
                "strategy": "IFS_SMC_2.0"
            }

        return None
