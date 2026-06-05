"""
🧠 Entrenador ML (Random Forest Predictor)
============================================
Machine Learning offline. Descarga el mercado, calcula anomalías,
y entrena un clasificador para decir si un setup técnico subirá o bajará.
Guarda su "cerebro" en models/rf_model.pkl
"""

import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ML Libraries
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))

class MLTrainer:
    def __init__(self, symbol="US100.cash", timeframe=mt5.TIMEFRAME_M15, bars=10000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
    def run(self):
        print(f"🤖 ENTRENAMIENTO IA INICIANDO ({self.symbol})...")
        
        # 1. Fetch Data (Desde disco local para aprovechar la GPU al máximo)
        import glob
        print(f"📥 Leyendo datos locales de disco duro para {self.symbol}...")
        
        # Buscar en data/raw los archivos parquet (generados por 01_download_data.py)
        raw_dir = os.path.join(MODEL_DIR, "raw")
        archivos = glob.glob(os.path.join(raw_dir, f"{self.symbol}_*.parquet"))
        
        if not archivos:
            print(f"❌ No se encontraron archivos .parquet para {self.symbol} en {raw_dir}")
            print("💡 Ejecuta python scripts/01_download_data.py primero.")
            return
            
        print(f"📚 Encontrados {len(archivos)} archivos. Consolidando...")
        df_list = [pd.read_parquet(archivo) for archivo in archivos]
        df = pd.concat(df_list, ignore_index=True)
        
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.sort_values('time').reset_index(drop=True)
            
        print(f"✅ Cargadas {len(df):,} velas históricas en memoria RAM.")
        
        # 2. Feature Engineering (Crear las variables que la IA estudiará)
        print("🧠 Calculando Features (RSI, Volatilidad, Diferenciales EMA, Horarios)...")
        
        # Variables de tiempo (El mercado se comporta distinto a las 3am vs 10am)
        df['hour'] = df['time'].dt.hour
        df['minute'] = df['time'].dt.minute
        df['day_of_week'] = df['time'].dt.dayofweek
        
        # Técnicos básicos
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_dist'] = df['ema20'] - df['ema50'] # Distancia en puntos reales
        
        # Z-Score (Reversión a la media)
        sma50 = df['close'].rolling(50).mean()
        std50 = df['close'].rolling(50).std()
        df['zscore'] = (df['close'] - sma50) / (std50 + 1e-9)

        # ATR (Volatilidad dinámica real)
        tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        
        # ADX (Fuerza de la tendencia)
        plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
        minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)
        plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
        atr_adx = tr.ewm(alpha=1/14, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
        minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
        df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
        
        # MACD Momentum
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        df['volatility'] = df['high'] - df['low']
        
        # Variables de Momentum (RSI)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Variables de Tendencia Pasada
        df['return_last_3'] = df['close'] - df['close'].shift(3)
        
        # 3. Labeling (Path-Dependent: Considera el Stop Loss)
        # Ventana futura de 100 velas (Igual al motor del Backtester)
        # Shift negativo trae los datos futuros al presente
        future_high = df['high'].shift(-1)[::-1].rolling(100, min_periods=1).max()[::-1]
        future_low = df['low'].shift(-1)[::-1].rolling(100, min_periods=1).min()[::-1]
        
        tp = 40.0 # Take Profit (40 puntos)
        sl = 20.0 # Stop Loss (20 puntos)
        
        conditions = [
            # COMPRA: Toca TP hacia arriba Y NUNCA toca SL hacia abajo en esas 12 velas
            ((future_high - df['close']) >= tp) & ((df['close'] - future_low) < sl),
            # VENTA: Toca TP hacia abajo Y NUNCA toca SL hacia arriba en esas 12 velas
            ((df['close'] - future_low) >= tp) & ((future_high - df['close']) < sl)
        ]
        choices = [2, 0]
        df['target'] = np.select(conditions, choices, default=1)
        
        # Limpiar NaN y valores extremos
        df = df.dropna().replace([np.inf, -np.inf], np.nan).dropna()
        
        # Filtrar el ruido. La IA aprenderá mejor si solo le mostramos los movimientos claros (1 y -1)
        # Quitar los casos '0' ayuda mucho al accuracy predictivo si usamos "Probability" output
        # Pero para un clasificador general dejaremos todo, o daremos pesos a las clases.
        
        features = ['hour', 'day_of_week', 'ema_dist', 'volatility', 'rsi', 'return_last_3', 'zscore', 'atr', 'adx', 'macd_hist']
        X = df[features]
        y = df['target']
        
        # 4. Train Test Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        print(f"📊 Dataset listo: {len(X_train)} Train | {len(X_test)} Test")
        
        # 5. Entrenar XGBoost con RTX 5070
        print("⚙️ Entrenando XGBoost con Aceleración CUDA (RTX 5070)...")
        rf = xgb.XGBClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.01,
            tree_method="hist",
            device="cuda",
            random_state=42
        )
        rf.fit(X_train, y_train)
        
        # 6. Evaluación
        y_pred = rf.predict(X_test)
        print("\n=== REPORTE DE CLASIFICACIÓN DE LA IA ===")
        print(classification_report(y_test, y_pred))
        
        acc = accuracy_score(y_test, y_pred)
        print(f"🎯 Precisión Pura en Test Inédito: {acc*100:.1f}%\n")
        
        # 7. Guardar el Modelo (Cerebro .pkl)
        model_path = os.path.join(MODEL_DIR, f"rf_model_{self.symbol}.pkl")
        joblib.dump(rf, model_path)
        print(f"✅ CEREBRO GUARDADO EN: {model_path}")
        print("📌 Tu bot ahora puede importar strategy/ml_random_forest.py para leer el mercado con IA en tiempo real.")

if __name__ == "__main__":
    trainer = MLTrainer()
    trainer.run()
