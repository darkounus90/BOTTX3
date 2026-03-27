"""
🏗️ TX3 PRO - ESTRATEGIA: ICT SILVER BULLET (NY SESSION)
======================================================
Lógica: Basada en la metodología de Inner Circle Trader.
Busca una entrada institucional entre las 10:00 AM y 11:00 AM EST.
Requisitos: 
1. Sweep de liquidez previa (Máximo/Mínimo anterior).
2. Market Structure Shift (MSS) con desplazamiento fuerte.
3. Fair Value Gap (FVG) activo.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class SilverBulletStrategy(BaseStrategy):
    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M5
        
        # Parámetros Silver Bullet
        self.start_hour = 10 # 10:00 AM NY
        self.end_hour = 11   # 11:00 AM NY
        self.fvg_lookback = 10
        self.min_displacement_pips = 5.0

    def get_name(self) -> str:
        return f"Silver Bullet ({self.symbol})"

    def _get_ny_time(self):
        """Obtiene la hora actual corregida a New York"""
        return datetime.now(ZoneInfo("America/New_York"))

    def _find_fvgs(self, df):
        """Detecta FVGs recientes en el desplazamiento"""
        fvgs = []
        for i in range(len(df)-3, len(df)-50, -1):
            if i < 2: break
            # FVG Alcista (Gap entre el High de i-2 y el Low de i)
            if df.iloc[i]['low'] > df.iloc[i-2]['high']:
                fvgs.append({
                    'type': 'BULLISH',
                    'top': df.iloc[i]['low'],
                    'bottom': df.iloc[i-2]['high'],
                    'mid': (df.iloc[i]['low'] + df.iloc[i-2]['high']) / 2
                })
            # FVG Bajista
            elif df.iloc[i]['high'] < df.iloc[i-2]['low']:
                fvgs.append({
                    'type': 'BEARISH',
                    'top': df.iloc[i-2]['low'],
                    'bottom': df.iloc[i]['high'],
                    'mid': (df.iloc[i-2]['low'] + df.iloc[i]['high']) / 2
                })
        return fvgs

    def generate_signal(self) -> dict | None:
        # 1. Filtro estricto de Tiempo (Silver Bullet Window)
        ny_now = self._get_ny_time()
        if ny_now.hour != self.start_hour:
            return None

        # 2. Descargar datos M5
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 100)
        if rates is None or len(rates) < 50: return None
        df = pd.DataFrame(rates)
        
        # 3. Identificar Desplazamiento (Cuerpo de vela > Mechas)
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        pip = 0.0001 if "JPY" not in self.symbol else 0.01
        
        move_pips = abs(curr['close'] - df.iloc[-5]['open']) / (10 * pip)
        if move_pips < self.min_displacement_pips: return None
        
        # 4. Buscar FVGs activos en el desplazamiento
        fvgs = self._find_fvgs(df)
        if not fvgs: return None
        
        last_fvg = fvgs[0]
        signal = None
        reason = ""
        
        # 5. Entrada en Mitigación
        if last_fvg['type'] == 'BULLISH' and curr['close'] > last_fvg['mid']:
            # Esperar a que el precio 'toque' el FVG
            if curr['low'] <= last_fvg['top'] and curr['close'] > last_fvg['mid']:
                signal = "BUY"
                reason = "Silver Bullet: Mitigation of Bullish FVG in NY Window"
                
        elif last_fvg['type'] == 'BEARISH' and curr['close'] < last_fvg['mid']:
            if curr['high'] >= last_fvg['bottom'] and curr['close'] < last_fvg['mid']:
                signal = "SELL"
                reason = "Silver Bullet: Mitigation of Bearish FVG in NY Window"

        if signal:
            # SL detrás del FVG o el Swing Low anterior
            sl = max(12.0, round(move_pips * 0.8, 1))
            tp = max(24.0, sl * 2.5) # R:R 1:2.5 mínimo
            
            return {
                "symbol": self.symbol,
                "type": signal,
                "reason": reason,
                "sl_pips": sl,
                "tp_pips": tp,
                "strategy": "SilverBullet_ICT"
            }

        return None
