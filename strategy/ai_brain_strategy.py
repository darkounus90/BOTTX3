import os
import joblib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class AIBrainStrategy(BaseStrategy):
    """
    🧠 BrainForge Strategy V3 (Institucional)
    Estrategia que lee el modelo entrenado con Optuna y Triple Barrera.
    """
    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        
        # Cargar Cerebro V3
        model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_lab', 'models', 'brain_v3.pkl'))
        self.model = None
        
        if os.path.exists(model_path):
            self.model = joblib.load(model_path)
            try:
                self.model.set_params(device="cpu")
            except:
                pass
            self.logger.info(f"🧠 Cerebro BrainForge V3 Cargado Exitosamente para {self.symbol}.")
        else:
            self.logger.error(f"❌ Cerebro V3 no encontrado en {model_path}.")
            
        self.bars_needed = 250
        self.confidence_threshold = 0.25 # Mismo umbral del simulador Monte Carlo
        
    def get_name(self) -> str:
        return f"BrainForge V3 ({self.symbol})"

    def _calc_rsi(self, series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))

    def _calc_atr(self, df, period=14):
        tr1 = df['high'] - df['low']
        tr2 = (df['high'] - df['close'].shift()).abs()
        tr3 = (df['low'] - df['close'].shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period, min_periods=1).mean()

    def generate_signal(self) -> dict | None:
        if not self.model:
            return None
            
        # RECOMENDACIÓN: Desactivar la IA para pares que no sean EURUSD
        if self.symbol != "EURUSD":
            return None
            
        # 1. Obtener Datos
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # 2. Reconstruir Features de Tiempo Real (Idéntico a 02_build_features.py V3)
        PIP_SIZE = 0.0001
        
        df['hour'] = df['time'].dt.hour
        df['day_of_week'] = df['time'].dt.dayofweek
        
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['sma200'] = df['close'].rolling(200).mean()
        
        df['dist_ema9_21_pips'] = (df['ema9'] - df['ema21']) / PIP_SIZE
        df['dist_close_ema50_pips'] = (df['close'] - df['ema50']) / PIP_SIZE
        df['dist_close_sma200_pips'] = (df['close'] - df['sma200']) / PIP_SIZE
        
        df['rsi14'] = self._calc_rsi(df['close'], 14)
        rsi_min = df['rsi14'].rolling(14).min()
        rsi_max = df['rsi14'].rolling(14).max()
        df['stoch_rsi'] = (df['rsi14'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
        
        df['atr14_pips'] = self._calc_atr(df, 14) / PIP_SIZE
        
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = (ema12 - ema26) / PIP_SIZE
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        sma20 = df['close'].rolling(20).mean()
        std20 = df['close'].rolling(20).std()
        df['bbw'] = (std20 * 4) / sma20
        df['zscore20'] = (df['close'] - sma20) / (std20 + 1e-9)
        
        df['roc_15'] = df['close'].pct_change(15) * 100
        df['roc_30'] = df['close'].pct_change(30) * 100
        
        df['return_1_pips'] = df['close'].diff(1) / PIP_SIZE
        df['return_3_pips'] = df['close'].diff(3) / PIP_SIZE
        df['return_5_pips'] = df['close'].diff(5) / PIP_SIZE
        
        # 3. Extraer vela cerrada (la penúltima vela)
        last_bar = df.iloc[-2]
        
        # Vector exacto
        features_list = [
            'tick_volume', 'spread',
            'hour', 'day_of_week', 
            'ema9', 'ema21', 'ema50', 'sma200',
            'dist_ema9_21_pips', 'dist_close_ema50_pips', 'dist_close_sma200_pips',
            'rsi14', 'stoch_rsi', 'atr14_pips', 
            'macd', 'macd_signal', 'macd_hist', 
            'bbw', 'zscore20', 
            'roc_15', 'roc_30',
            'return_1_pips', 'return_3_pips', 'return_5_pips'
        ]
        
        X_live = df[features_list].iloc[-2:-1]
        
        # 4. Inferencia
        try:
            probs = self.model.predict_proba(X_live)[0]
            prob_win = probs[2] 
        except Exception as e:
            self.logger.error(f"Fallo predictivo AI: {e}")
            return None
        
        if prob_win < self.confidence_threshold:
            return None
            
        # Deduplicación de señales
        current_candle_time = last_bar['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time
        
        tp_pips = 40.0
        sl_pips = 20.0
        
        ts_signal = {
            "signal": "BUY",
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": f"BrainForge V3 (Confianza {prob_win*100:.1f}%)"
        }
        
        self.log_signal(ts_signal)
        return ts_signal
