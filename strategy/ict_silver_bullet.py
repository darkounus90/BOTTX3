"""
🏗️ TX3 PRO - ESTRATEGIA: ICT SILVER BULLET (NY SESSION)
======================================================
Lógica: Basada en la metodología de Inner Circle Trader.
Busca una entrada institucional entre las 10:00 AM y 11:00 AM EST.
Filtros Elite:
1. Sweep de liquidez previa en H1 (ventana de 6h).
2. Desplazamiento institucional genuino (> 8 pips).
3. Mitigación de FVG en M5.
4. Un solo tiro por sesión para evitar overtrading.
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
        
        # Parámetros Silver Bullet (Ajuste Fino EURUSD)
        self.start_hour = 10 
        self.end_hour = 11   
        self.fvg_lookback = 10
        self.min_displacement_pips = 6.0 # Ajuste Elite: Captura más Balas de Plata
        self.last_trade_date = None

    def get_name(self) -> str:
        return f"SilverBullet_Elite_{self.symbol}"

    def _get_ny_time(self):
        """Obtiene la hora actual corregida a New York"""
        return datetime.now(ZoneInfo("America/New_York"))

    def _find_fvgs(self, df):
        """Detecta FVGs recientes en el desplazamiento"""
        fvgs = []
        for i in range(len(df)-1, 1, -1):
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
        # 1. Filtro estricto de Tiempo + Un solo tiro
        ny_now = self._get_ny_time()
        today = ny_now.date()
        if ny_now.hour != self.start_hour or self.last_trade_date == today:
            return None

        # 2. Obtener Liquidez H1 (Radar de Londres + Apertura Wall Street)
        h1_rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_H1, 0, 6)
        if h1_rates is None or len(h1_rates) < 4: return None
        # Excluimos la vela actual para ver niveles fijos
        liq_high = max([r['high'] for r in h1_rates[:-1]])
        liq_low = min([r['low'] for r in h1_rates[:-1]])

        # 3. Descargar datos M5
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 50)
        if rates is None or len(rates) < 30: return None
        df = pd.DataFrame(rates)
        
        # 4. Verificar Barrido de Liquidez previo (Sweep)
        curr = df.iloc[-1]
        pip = 0.0001 if "JPY" not in self.symbol else 0.01
        
        has_swept_high = df['high'].iloc[-40:].max() > liq_high
        has_swept_low = df['low'].iloc[-40:].min() < liq_low
        
        # 5. Desplazamiento e Impulso (Filtro de 8 pips)
        move_pips = abs(curr['close'] - df.iloc[-5]['open']) / (10 * pip)
        if move_pips < self.min_displacement_pips: return None
        
        # 6. Buscar FVGs
        fvgs = self._find_fvgs(df)
        if not fvgs: return None
        
        last_fvg = fvgs[0]
        signal = None
        reason = ""
        
        # COMPRA: Post-Sweep Low + Bullish FVG Mitigation
        if has_swept_low and last_fvg['type'] == 'BULLISH':
            if curr['low'] <= last_fvg['top'] and curr['close'] > last_fvg['mid']:
                signal = "BUY"
                reason = "S.B. Elite: Post-Sweep Bullish FVG Mitigation (8+ pips move)"
                
        # VENTA: Post-Sweep High + Bearish FVG Mitigation
        elif has_swept_high and last_fvg['type'] == 'BEARISH':
            if curr['high'] >= last_fvg['bottom'] and curr['close'] < last_fvg['mid']:
                signal = "SELL"
                reason = "S.B. Elite: Post-Sweep Bearish FVG Mitigation (8+ pips move)"

        if signal:
            self.last_trade_date = today
            sl = max(12.0, round(move_pips * 0.7, 1))
            tp = max(30.0, sl * 2.5) 
            
            return {
                "symbol": self.symbol,
                "signal": signal,
                "reason": reason,
                "stop_loss_pips": sl,
                "take_profit_pips": tp,
                "strategy": "SilverBullet_ICT_Elite"
            }

        return None
