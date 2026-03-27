"""
🏗️ TX3 PRO - ESTRATEGIA: LONDON OPEN PURGE (SMC 2.1)
===================================================
Versión Institucional Optimizada para EURUSD.
Lógica: Ataca la manipulación algorítmica de los bancos de Londres.
1. Define el Asia Range (Techo/Suelo de Tokio).
2. Detecta el barrido (Hunt) en la apertura de Londres (03:00 - 05:00 EST).
3. Entrada tras el Market Structure Shift (MSS) + FVG.
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, time
from zoneinfo import ZoneInfo
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class LondonOpenPurgeStrategy(BaseStrategy):
    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M5
        
        # Parámetros Institucionales SMC 2.1
        self.asia_start_hour = 19 # 7 PM EST
        self.asia_end_hour = 2    # 2 AM EST
        self.london_start_hour = 3 # 3 AM EST (London Start)
        self.london_end_hour = 5   # 5 AM EST (End of Purge Window)
        
        self.min_displacement_pips = 5.5 # Ajuste Institucional: Captura más Londres
        self.last_trade_date = None

    def get_name(self) -> str:
        return f"LondonPurge_SMC21_{self.symbol}"

    def _get_ny_time(self):
        """Obtiene la hora actual corregida a New York (EST)"""
        return datetime.now(ZoneInfo("America/New_York"))

    def _get_session_range(self, df):
        """Identifica el máximo y mínimo del rango asiático (SMC Workflow)"""
        # Sincronizamos con el servidor del broker (Praga -> NY)
        df['dt'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize(BotConfig.FTMO_TIMEZONE).dt.tz_convert("America/New_York")
        asia_mask = (df['dt'].dt.hour >= self.asia_start_hour) | (df['dt'].dt.hour < self.asia_end_hour)
        asia_df = df[asia_mask]
        
        if len(asia_df) < 20: return None, None
        return asia_df['high'].max(), asia_df['low'].min()

    def generate_signal(self) -> dict | None:
        ny_now = self._get_ny_time()
        today = ny_now.date()
        
        # 1. Filtro de Ventana Horaria (Solo Londres Operativo)
        if not (self.london_start_hour <= ny_now.hour <= self.london_end_hour):
            return None
            
        if self.last_trade_date == today:
            return None

        # 2. Obtener Datos (Lookback amplio para ver Asia)
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 300)
        if rates is None or len(rates) < 150: return None
        df = pd.DataFrame(rates)
        
        # 3. Detectar Rangos
        asia_high, asia_low = self._get_session_range(df)
        if not asia_high: return None
        
        # 4. Verificar Barrido (Liquidity Sweep)
        curr = df.iloc[-1]
        pip = 0.0001 if "JPY" not in self.symbol else 0.01
        
        has_swept_high = df['high'].iloc[-30:].max() > asia_high
        has_swept_low = df['low'].iloc[-30:].min() < asia_low
        
        # 5. Buscar Desequilibrio (FVG)
        fvgs = []
        for i in range(len(df)-1, len(df)-20, -1):
            if i < 3: break
            # FVG Alcista (Tras sweep de bajos)
            if df.iloc[i]['low'] > df.iloc[i-2]['high']:
                fvgs.append({'type': 'BULLISH', 'top': df.iloc[i]['low'], 'bottom': df.iloc[i-2]['high']})
            # FVG Bajista (Tras sweep de altos)
            elif df.iloc[i]['high'] < df.iloc[i-2]['low']:
                fvgs.append({'type': 'BEARISH', 'top': df.iloc[i-2]['low'], 'bottom': df.iloc[i]['high']})
        
        if not fvgs: return None
        last_fvg = fvgs[0]
        
        # 6. Gatillo: Regreso al Rango + Mitigación
        signal = None
        reason = ""
        
        move_pips = abs(curr['close'] - df.iloc[-5]['open']) / (10 * pip)
        
        if has_swept_low and last_fvg['type'] == 'BULLISH' and curr['close'] > asia_low:
            if move_pips >= self.min_displacement_pips:
                signal = "BUY"
                reason = "London Purge: Asia Low Swept + Recovery M5 FVG"
                
        elif has_swept_high and last_fvg['type'] == 'BEARISH' and curr['close'] < asia_high:
            if move_pips >= self.min_displacement_pips:
                signal = "SELL"
                reason = "London Purge: Asia High Swept + Recovery M5 FVG"

        if signal:
            self.last_trade_date = today
            sl = max(12.0, round(move_pips * 0.8, 1))
            tp = max(36.0, sl * 3.0) # Apuntamos a un 1:3 institucional en el Euro
            
            return {
                "symbol": self.symbol,
                "signal": signal,
                "reason": reason,
                "stop_loss_pips": sl,
                "take_profit_pips": tp,
                "strategy": "LondonPurge_SMC21"
            }

        return None
