import os
import joblib
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import torch
import torch.nn as nn

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

# Misma arquitectura compacta que el laboratorio
class LSTMBrainNet(nn.Module):
    def __init__(self, input_size, hidden_size=32, num_layers=1, num_classes=3, dropout=0.5):
        super(LSTMBrainNet, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.fc1 = nn.Linear(hidden_size, 16)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(16, num_classes)
        
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = out[:, -1, :] 
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out

class AIBrainStrategy(BaseStrategy):
    """
    🧠 BrainForge Strategy V5 (Deep Learning LSTM Curado)
    Estrategia que evalúa secuencias de 60 velas usando PyTorch.
    Umbral de confianza ajustado al 40% (Sniper Mode).
    """
    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M15
        
        # Cargar Cerebro V5 LSTM y Scaler
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_lab', 'models'))
        model_path = os.path.join(base_dir, 'brain_v5_lstm.pth')
        scaler_path = os.path.join(base_dir, 'scaler_v5.pkl')
        
        self.model = None
        self.scaler = None
        self.seq_length = 60
        
        if os.path.exists(model_path) and os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
            # Inferencia siempre en CPU (mucho más rápido para 1 sola predicción en vivo)
            self.device = torch.device('cpu') 
            self.model = LSTMBrainNet(input_size=29) # 29 features estacionarias
            self.model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
            self.model.eval()
            self.logger.info(f"🧠 Cerebro Deep Learning V5 Cargado Exitosamente para {self.symbol}.")
        else:
            self.logger.warning(f"⏳ Cerebro V5 no encontrado. Asegúrate de haber entrenado el modelo localmente.")

        self.bars_needed = 250
        # UMBRAL SNIPER: Probado que por encima del 40% genera Profit Factor 1.64
        self.confidence_threshold = 0.40 
        
    def get_name(self) -> str:
        return f"BrainForge V5 LSTM ({self.symbol})"

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
            
        if self.symbol != "EURUSD":
            return None
            
        # 1. Obtener Datos
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # 2. Reconstruir Features de Tiempo Real (Sólo ESTACIONARIAS)
        PIP_SIZE = 0.0001
        
        # Variables cíclicas de tiempo
        hours = df['time'].dt.hour + (df['time'].dt.minute / 60.0)
        df['hour_sin'] = np.sin(2 * np.pi * hours / 24.0)
        df['hour_cos'] = np.cos(2 * np.pi * hours / 24.0)
        days = df['time'].dt.dayofweek
        df['day_sin'] = np.sin(2 * np.pi * days / 5.0)
        df['day_cos'] = np.cos(2 * np.pi * days / 5.0)
        
        # Medias y distancias relativas
        ema9 = df['close'].ewm(span=9, adjust=False).mean()
        ema21 = df['close'].ewm(span=21, adjust=False).mean()
        ema50 = df['close'].ewm(span=50, adjust=False).mean()
        sma200 = df['close'].rolling(200).mean()
        ema_H1_50 = df['close'].ewm(span=200, adjust=False).mean()
        sma_H4_200 = df['close'].rolling(3200).mean()
        
        df['dist_ema9_21_pips'] = (ema9 - ema21) / PIP_SIZE
        df['dist_close_ema50_pips'] = (df['close'] - ema50) / PIP_SIZE
        df['dist_close_sma200_pips'] = (df['close'] - sma200) / PIP_SIZE
        df['dist_macro_H1_pips'] = (df['close'] - ema_H1_50) / PIP_SIZE
        df['dist_macro_H4_pips'] = (df['close'] - sma_H4_200) / PIP_SIZE
        
        # Osciladores
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
        
        # Price Action SMC
        df['body_size_pips'] = (df['close'] - df['open']).abs() / PIP_SIZE
        df['candle_dir'] = np.where(df['close'] >= df['open'], 1, -1)
        df['upper_wick_pips'] = (df['high'] - df[['open', 'close']].max(axis=1)) / PIP_SIZE
        df['lower_wick_pips'] = (df[['open', 'close']].min(axis=1) - df['low']) / PIP_SIZE
        total_range = (df['high'] - df['low']) / PIP_SIZE
        df['wick_rejection_ratio'] = (df['upper_wick_pips'] + df['lower_wick_pips']) / (total_range + 1e-9)
        
        last_bar = df.iloc[-2]
        
        features_list = [
            'tick_volume', 'spread',
            'hour_sin', 'hour_cos', 'day_sin', 'day_cos', 
            'dist_ema9_21_pips', 'dist_close_ema50_pips', 'dist_close_sma200_pips',
            'dist_macro_H1_pips', 'dist_macro_H4_pips',
            'rsi14', 'stoch_rsi', 'atr14_pips', 
            'macd', 'macd_signal', 'macd_hist', 
            'bbw', 'zscore20', 
            'roc_15', 'roc_30',
            'return_1_pips', 'return_3_pips', 'return_5_pips',
            'body_size_pips', 'candle_dir', 'upper_wick_pips', 
            'lower_wick_pips', 'wick_rejection_ratio'
        ]
        
        X_live = df[features_list].iloc[-self.seq_length - 1:-1].values
        
        if len(X_live) != self.seq_length:
            return None
            
        try:
            X_scaled = self.scaler.transform(X_live)
            X_tensor = torch.tensor(X_scaled, dtype=torch.float32).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(X_tensor)
                probs = torch.softmax(outputs, dim=1)[0]
                prob_win = probs[2].item()
                
        except Exception as e:
            self.logger.error(f"Fallo predictivo AI PyTorch: {e}")
            return None
        
        if prob_win < self.confidence_threshold:
            return None
            
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
            "reason": f"BrainForge V5 LSTM (Confianza {prob_win*100:.1f}%)"
        }
        
        self.log_signal(ts_signal)
        return ts_signal
