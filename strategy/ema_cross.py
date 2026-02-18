"""
📈 Trend Hunter Pro Strategy (EMA Cross Enhanced)
==================================================
Estrategia profesional de seguimiento de tendencia.
Combina cruce de EMAs en M15 con filtro de tendencia mayor (H1)
y fuerza de tendencia (ADX) para filtrar mercados laterales.

Reglas de Entrada:
1. Cruce EMA 20/50 en M15 (Señal base)
2. Precio > EMA 200 en H1 (Filtro de Tendencia Mayor - Solo Compras)
3. Precio < EMA 200 en H1 (Filtro de Tendencia Mayor - Solo Ventas)
4. ADX(14) > 20 (Filtro de Volatilidad - Evita Rangos)

Gestión de Salida:
- SL dinámico: 1.5 * ATR (ajustado a la volatilidad real del momento)
- TP dinámico: 3.0 * ATR (Ratio 1:2 mínimo)
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger


class EMACrossStrategy(BaseStrategy):
    """
    Estrategia Trend Hunter Pro.
    
    Timeframes: 
    - M15 (Gatillo) 
    - H1 (Filtro de Tendencia)
    
    Indicadores:
    - EMA 20, 50, 200
    - ADX 14
    - ATR 14
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        self.trend_timeframe = mt5.TIMEFRAME_H1
        
        # Parámetros
        self.ema_fast = BotConfig.EMA_FAST_PERIOD      # 20
        self.ema_slow = BotConfig.EMA_SLOW_PERIOD       # 50
        self.ema_trend = 200                             # Filtro Tendencia H1
        self.adx_period = 14                             # Fuerza Tendencia
        self.adx_threshold = 20                          # Mínimo ADX para operar
        self.atr_period = 14                             # Volatilidad
        self.bars_needed = 300                           # Histórico necesario
        self.max_spread_pips = 3.0

        self.logger.info(
            f"🚀 Trend Hunter Pro Strategy inicializada | {self.symbol}\n"
            f"   M15: EMA {self.ema_fast}/{self.ema_slow} + ADX > {self.adx_threshold}\n"
            f"   H1:  Filtro EMA {self.ema_trend} (Tendencia Mayor)"
        )

    def get_name(self) -> str:
        return f"Trend Hunter Pro (M15+H1)"

    def _get_data(self, timeframe):
        """Obtiene datos históricos probados"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def _calculate_indicators(self, df):
        """Calcula EMAs, ATR y ADX"""
        # EMAs
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        df['ema_trend'] = df['close'].ewm(span=self.ema_trend, adjust=False).mean()

        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=self.atr_period).mean()

        # ADX
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr_smooth = true_range.rolling(window=self.adx_period).sum()
        plus_di = 100 * (plus_dm.ewm(alpha=1/self.adx_period).mean() / tr_smooth)
        minus_di = 100 * (abs(minus_dm).ewm(alpha=1/self.adx_period).mean() / tr_smooth)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        df['adx'] = dx.ewm(alpha=1/self.adx_period).mean()
        
        return df

    def generate_signal(self) -> dict | None:
        """Genera señal con lógica profesional Multi-Timeframe"""
        
        # 1. Obtener Datos M15 y H1
        df_m15 = self._get_data(self.timeframe)
        df_h1 = self._get_data(self.trend_timeframe)
        
        if df_m15 is None or df_h1 is None:
            return None

        # 2. Calcular Indicadores
        df_m15 = self._calculate_indicators(df_m15)
        # Para H1 solo necesitamos la EMA 200 de tendencia
        df_h1['ema_trend'] = df_h1['close'].ewm(span=self.ema_trend, adjust=False).mean()

        # 3. Analizar Mercado Actual
        curr = df_m15.iloc[-1]
        prev = df_m15.iloc[-2]
        prev2 = df_m15.iloc[-3]
        
        trend_h1 = df_h1.iloc[-1] # Última vela cerrada H1
        
        # 4. Filtros de Tendencia y Volatilidad
        # H1 Trend Filter: Precio H1 vs EMA 200 H1
        is_uptrend_h1 = trend_h1['close'] > trend_h1['ema_trend']
        is_downtrend_h1 = trend_h1['close'] < trend_h1['ema_trend']
        
        # ADX Filter: Evitar rangos
        avg_adx = curr['adx']
        if avg_adx < self.adx_threshold:
            # Mercado lateral / sin fuerza
            return None

        # 5. Detectar Cruce M15
        bullish_cross = (prev['ema_fast'] > prev['ema_slow']) and (prev2['ema_fast'] <= prev2['ema_slow'])
        bearish_cross = (prev['ema_fast'] < prev['ema_slow']) and (prev2['ema_fast'] >= prev2['ema_slow'])
        
        if not bullish_cross and not bearish_cross:
            return None

        # 6. Validar Señal con Tendencia Mayor (H1)
        signal_type = None
        
        if bullish_cross and is_uptrend_h1:
            signal_type = "BUY"
        elif bearish_cross and is_downtrend_h1:
            signal_type = "SELL"
        else:
            self.logger.info(f"Cruce { 'Alcista' if bullish_cross else 'Bajista'} ignorado por tendencia opuesta en H1")
            return None

        # 7. Calcular SL/TP Dinámicos con ATR
        # Usamos ATR de M15 para ajustar al ruido local
        atr_value = curr['atr']
        if pd.isna(atr_value) or atr_value <= 0:
            atr_value = 0.0010 # Fallback 10 pips

        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point if symbol_info else 0.00001
        
        # ATR Multipliers: SL 1.5x, TP 5.0x (Home Run Strategy ⚾️)
        sl_dist = atr_value * 1.5
        tp_dist = atr_value * 5.0
        
        sl_pips = round(sl_dist / (10 * point), 1)
        tp_pips = round(tp_dist / (10 * point), 1)
        
        # Mínimos de seguridad del broker
        sl_pips = max(sl_pips, 5.0)
        tp_pips = max(tp_pips, 10.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": (
                f"Cruce M15 + Tendencia H1 ({'Alcista' if is_uptrend_h1 else 'Bajista'}) | "
                f"ADX: {avg_adx:.1f} (Fuerte) | ATR SL: {sl_pips} pips"
            )
        }
        
        self.log_signal(ts_signal)
        return ts_signal
