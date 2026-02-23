"""
📈 Dynamic Momentum Pro Strategy
==================================================
Estrategia profesional adaptativa.
Combina cruce de EMAs, Pullbacks a la media (Mean Reversion en Tendencia)
y filtro de Momentum (RSI + ADX) con alineación Multi-Timeframe (H1).

Reglas de Entrada (Compra):
1. Tendencia Mayor H1 Alcista (Precio > EMA 200)
2. Filtro de Mercado: ADX > 15 (Evitar rangos muy estrechos)
3. Gatillo A (Cruce): Cruzamiento reciente rápido EMA 20 > EMA 50
   O Gatillo B (Pullback): EMA 20 > EMA 50 pero el precio rebotó sobre la EMA 20 (RSI < 70).

Reglas de Salida:
- SL dinámico y TP calculados por la volatilidad actual usando ATR(14).
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger


class EMACrossStrategy(BaseStrategy):
    """
    Estrategia Dynamic Momentum Pro.
    Genera señales de alta precisión y mayor frecuencia al 
    añadir pullbacks direccionales.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        # Usamos M5 o M15 dependiendo de BotConfig (por defecto M15)
        # Adaptado a M5/M15 para que sea más reactivo si se prueba en horas.
        self.timeframe = mt5.TIMEFRAME_M5 if "M5" in BotConfig.DEFAULT_TIMEFRAME else mt5.TIMEFRAME_M15
        self.trend_timeframe = mt5.TIMEFRAME_H1
        
        # Parámetros Profesionales
        self.ema_fast = BotConfig.EMA_FAST_PERIOD      # 20
        self.ema_slow = BotConfig.EMA_SLOW_PERIOD       # 50
        self.ema_trend = 200                             # Filtro Tendencia H1
        self.adx_period = 14                             
        self.adx_threshold = 18                          # Aumentado para eliminar ruido en M5
        self.rsi_period = 14
        self.atr_period = 14                             
        self.bars_needed = 300                           
        self.last_processed_time = None                  # Optimización VPS: Cache de última vela evaluada

        self.logger.info(
            f"🚀 Dynamic Momentum Pro inicializada | {self.symbol}\n"
            f"   TF: {BotConfig.DEFAULT_TIMEFRAME} | EMAs: {self.ema_fast}/{self.ema_slow} | Filtros: ADX>{self.adx_threshold}, RSI, H1 Trend"
        )

    def get_name(self) -> str:
        return f"Dynamic Momentum Pro ({self.symbol})"

    def _get_data(self, timeframe):
        """Obtiene datos históricos probados"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def _calculate_indicators(self, df):
        """Calcula EMAs, ATR, ADX y RSI"""
        # EMAs
        df['ema_fast'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()

        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = true_range.rolling(window=self.atr_period).mean()

        # ADX (Simple implementation)
        plus_dm = df['high'].diff()
        minus_dm = df['low'].diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        
        tr_smooth = true_range.rolling(window=self.adx_period).sum()
        plus_di = 100 * (plus_dm.ewm(alpha=1/self.adx_period).mean() / tr_smooth)
        minus_di = 100 * (abs(minus_dm).ewm(alpha=1/self.adx_period).mean() / tr_smooth)
        dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
        df['adx'] = dx.ewm(alpha=1/self.adx_period).mean()

        # RSI calculation (Wilder's)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df

    def generate_signal(self) -> dict | None:
        """Genera señal basada en lógica Multi-Timeframe adaptativa"""
        import MetaTrader5 as mt5
        
        # ─── OPTIMIZACIÓN VPS (2CPU / 2GB RAM) ──────────────────────
        # Preguntar a MT5 por las últimas 2 velas es ultra-ligero (0.01 ms).
        # Si la vela cerrada más reciente es la misma que la última vez, 
        # abortamos y ahorramos el 99% del CPU evitando cálculos en Pandas.
        recent_rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 2)
        if recent_rates is None or len(recent_rates) < 2:
            return None
            
        last_closed_time = recent_rates[-2]['time']
        if self.last_processed_time == last_closed_time:
            return None # No hay vela nueva, no hacemos nada.
            
        # Si llegamos aquí, hay una nueva vela que evaluar (cada 5 min).
        self.last_processed_time = last_closed_time
        # ────────────────────────────────────────────────────────────

        df_base = self._get_data(self.timeframe)
        df_h1 = self._get_data(self.trend_timeframe)
        
        if df_base is None or df_h1 is None:
            return None

        df_base = self._calculate_indicators(df_base)
        df_h1['ema_trend'] = df_h1['close'].ewm(span=self.ema_trend, adjust=False).mean()

        # Usar la vela anterior cerrada prev (evitar falsos positivos en vela actual)
        prev = df_base.iloc[-2]
        prev2 = df_base.iloc[-3]
        curr_unclosed = df_base.iloc[-1]
        
        trend_h1 = df_h1.iloc[-2] # Última vela cerrada H1
        
        # Filtro de Tendencia H1
        is_uptrend_h1 = trend_h1['close'] > trend_h1['ema_trend']
        is_downtrend_h1 = trend_h1['close'] < trend_h1['ema_trend']
        
        # ADX Filter: Evitar mercados sin convicción
        if prev['adx'] < self.adx_threshold:
            return None

        # Condiciones Fundamentales de Estructura de Corto Plazo
        uptrend_base = prev['ema_fast'] > prev['ema_slow']
        downtrend_base = prev['ema_fast'] < prev['ema_slow']

        # DETECCIÓN DE GATILLOS
        # 1. Gatillo de Cruce
        bullish_cross = uptrend_base and (prev2['ema_fast'] <= prev2['ema_slow'])
        bearish_cross = downtrend_base and (prev2['ema_fast'] >= prev2['ema_slow'])

        # 2. Gatillo de Pullback (Rebote dinámico en la EMA)
        # Alcista: Tendencia definida, el precio estaba tocando/bajo la EMA rápida, y ahora cierra por encima con RSI sano (no sobrecomprado)
        bullish_pullback = uptrend_base and (prev2['close'] < prev2['ema_fast']) and (prev['close'] > prev['ema_fast']) and (prev['rsi'] > 40 and prev['rsi'] < 70)
        
        # Bajista: Tendencia definida, el precio estaba tocando/arriba de la EMA rápida, y ahora cierra por debajo con RSI sano (no sobrevendido)
        bearish_pullback = downtrend_base and (prev2['close'] > prev2['ema_fast']) and (prev['close'] < prev['ema_fast']) and (prev['rsi'] < 60 and prev['rsi'] > 30)

        signal_type = None
        reason = ""

        # Lógica Combinada (H1 tiene que estar alineado con la operativa)
        if (bullish_cross or bullish_pullback) and is_uptrend_h1:
            signal_type = "BUY"
            reason = "Cruce" if bullish_cross else "Pullback EMA"
        elif (bearish_cross or bearish_pullback) and is_downtrend_h1:
            signal_type = "SELL"
            reason = "Cruce" if bearish_cross else "Pullback EMA"
        else:
            return None

        # Gestión de Riesgo Dinámica Profesional
        atr_value = prev['atr']
        if pd.isna(atr_value) or atr_value <= 0:
            atr_value = 0.0010 

        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point if symbol_info else 0.00001
        
        # Ratios de R:R (Mejorados a 1:2 mínimo)
        sl_dist = atr_value * 1.5
        tp_dist = atr_value * 3.0  # Conservador-Profesional
        
        sl_pips = round(sl_dist / (10 * point), 1)
        tp_pips = round(tp_dist / (10 * point), 1)
        
        # Mínimos del broker y para evitar whipsaws
        sl_pips = max(sl_pips, BotConfig.DEFAULT_SL_PIPS)
        tp_pips = max(tp_pips, BotConfig.DEFAULT_TP_PIPS)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "adx": round(prev['adx'], 2),
            "reason": f"{reason} | H1 Trend Align | ADX: {prev['adx']:.1f} | RSI: {prev['rsi']:.1f} | SL: {sl_pips}p"
        }
        
        self.log_signal(ts_signal)
        return ts_signal

