"""
🧠 Machine Learning Random Forest Strategy
============================================
La estrategia definitiva. No opera dibujando cruces,
sino leyendo la memoria de la Inteligencia Artificial que
aprendió qué configuraciones rinden dinero en los últimos años.
"""

import os
import joblib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class MLRandomForestStrategy(BaseStrategy):
    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        
        # Cargar Cerebro
        model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', f'rf_model_{self.symbol}.pkl'))
        self.model = None
        
        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
            # Silenciar warning de GPU a CPU en modo en vivo
            if hasattr(self.model, 'set_params'):
                try:
                    self.model.set_params(device="cpu")
                except:
                    pass
            self.logger.info(f"🧠 Cerebro IA Cargado Exitosamente para {self.symbol}.")
        else:
            self.logger.error(f"❌ Cerebro no encontrado. Debes correr 'python scripts/train_ml_model.py' primero.")
            
        self.bars_needed = 60 # Solo necesita 60 barras para calcular RSI y EMAs actuales
        
    def get_name(self) -> str:
        return f"Random Forest AI Predictor ({self.symbol})"

    def generate_signal(self) -> dict | None:
        if not self.model:
            return None # Seguridad
            
        # 1. Obtener Datos
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # 2. Reconstruir Features de Tiempo Real (Tal como se entrenaron)
        last_bar = df.iloc[-2] # Evaluamos la vela anterior, ya 100% cerrada
        
        # Básicos
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_dist'] = df['ema20'] - df['ema50']
        
        # Z-Score
        sma50 = df['close'].rolling(50).mean()
        std50 = df['close'].rolling(50).std()
        df['zscore'] = (df['close'] - sma50) / (std50 + 1e-9)

        # ATR
        tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # ADX
        plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
        minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)
        plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
        atr_adx = tr.ewm(alpha=1/14, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        df['volatility'] = df['high'] - df['low']
        
        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Retorno
        df['return_last_3'] = df['close'] - df['close'].shift(3)
        
        # 3. Vector de Feature
        features = ['hour', 'day_of_week', 'ema_dist', 'volatility', 'rsi', 'return_last_3', 'zscore', 'atr', 'adx', 'macd_hist']
        X_live = df[features].iloc[-2:-1] # Extraer el vector correspondiente a last_bar
        
        # 4. PREDECIR EL FUTURO
        try:
            pred = self.model.predict(X_live)[0]
            prob = self.model.predict_proba(X_live)[0] # Array de probabilidad [baja, lateral, sube]
            max_prob = np.max(prob) * 100
        except Exception as e:
            self.logger.error(f"Fallo predictivo: {e}")
            return None
        
        # 5. Lógica de Riesgo (No operamos ruidos, ni cosas con menos 55% de certeza)
        if max_prob < 55:
            return None
            
        signal_type = None
        reason = ""
        
        if pred == 2:
            signal_type = "BUY"
            reason = f"IA Predictiva: Alcista (Certeza {max_prob:.1f}%)"
        elif pred == 0:
            signal_type = "SELL"
            reason = f"IA Predictiva: Bajista (Certeza {max_prob:.1f}%)"
        else:
            # pred == 1 (Lateral / Ruido)
            return None
            
        # 6. Salida Estándar
        # --- EVITAR SPAM EN LA MISMA VELA (Deduplicación) ---
        current_candle_time = last_bar['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        # TP y SL de 20 y 40 fijos, o dinámicos por ATR (por simplicidad, usar ATR o fijos fuertes)
        atr_value = df['high'].iloc[-14:] - df['low'].iloc[-14:]
        atr_mean = atr_value.mean()
        
        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point if symbol_info else 0.00001
        
        sl_dist = atr_mean * 1.5
        tp_dist = atr_mean * 3.0
        
        sl_pips = round(sl_dist / (10 * point), 1)
        tp_pips = round(tp_dist / (10 * point), 1)
        
        # Bound limits
        sl_pips = max(sl_pips, BotConfig.DEFAULT_SL_PIPS)
        tp_pips = max(tp_pips, BotConfig.DEFAULT_TP_PIPS)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }
        
        self.log_signal(ts_signal)
        return ts_signal
