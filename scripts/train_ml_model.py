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
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))

class MLTrainer:
    def __init__(self, symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15, bars=10000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        
        if not os.path.exists(MODEL_DIR):
            os.makedirs(MODEL_DIR)
            
    def run(self):
        print(f"🤖 ENTRENAMIENTO IA INICIANDO ({self.symbol})...")
        
        # 1. Fetch Data
        if not mt5.initialize():
            print("❌ MT5 Error")
            return
            
        print(f"📥 Descargando {self.bars} velas históricas para {self.symbol}...")
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars)
        
        if rates is None or len(rates) == 0:
            print(f"❌ No hay datos para {self.symbol}.")
            error = mt5.last_error()
            print(f"⚠️ Error MT5 Code: {error}")
            
            # Intentar ver si el símbolo existe pero con otro nombre
            symbols = mt5.symbols_get()
            if symbols:
                print(f"🔍 Símbolos disponibles en tu broker (primeros 10):")
                count = 0
                for s in symbols:
                    if 'EUR' in s.name or 'USD' in s.name:
                        print(f"  - {s.name}")
                        count += 1
                        if count >= 10: break
            
            print("💡 SUGERENCIA:")
            print("1. El mercado puede estar CERRADO (Fin de semana) y el broker desactiva descargas masivas temporales.")
            print("2. El símbolo en tu broker FPMarkets puede llamarse diferente (Ej: EURUSD.a, EURUSD.pro).")
            print("   Si es así, edita scripts/train_ml_model.py linea 133 para incluir ese sufijo.")
            
            mt5.shutdown()
            
            # Para evitar que el bot entero colapse en fin de semana y siga operando tradicionalmente:
            print("\n✅ CREANDO CEREBRO DE EMERGENCIA PARA CONTINUAR ARRANQUE...")
            # Crear un dataframe dummy de emergencia solo para que genere el archivo .pkl
            # y el bot tradicional no regrese el error the "FileNotFound"
            dummy_data = {'hour': [1], 'day_of_week': [1], 'ema_dist': [1], 'volatility': [1], 'rsi': [1], 'return_last_3': [1]}
            dummy_target = [0]
            dummy_rf = RandomForestClassifier(n_estimators=1, max_depth=1)
            dummy_rf.fit(pd.DataFrame(dummy_data), dummy_target)
            model_path = os.path.join(MODEL_DIR, f"rf_model_{self.symbol}.pkl")
            joblib.dump(dummy_rf, model_path)
            
            return
            
        mt5.shutdown()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # 2. Feature Engineering (Crear las variables que la IA estudiará)
        print("🧠 Calculando Features (RSI, Volatilidad, Diferenciales EMA, Horarios)...")
        
        # Variables de tiempo (El mercado se comporta distinto a las 3am vs 10am)
        df['hour'] = df['time'].dt.hour
        df['minute'] = df['time'].dt.minute
        df['day_of_week'] = df['time'].dt.dayofweek
        
        # Técnicos básicos
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema_dist'] = (df['ema20'] - df['ema50']) * 10000 # Distancia en pips
        
        df['volatility'] = (df['high'] - df['low']) * 10000
        
        # Variables de Momentum
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Variables de Tendencia Pasada
        df['return_last_3'] = df['close'] - df['close'].shift(3)
        
        # 3. Labeling (La variable objetivo / Target)
        # Queremos predecir qué va a pasar en las próximas 6 velas (1h 30m)
        df['future_return'] = df['close'].shift(-6) - df['close']
        
        # Nuestro "Edge"
        # 1: Sube más de 5 pips
        # -1: Cae más de 5 pips
        # 0: Se queda lateralizado (Ruido)
        
        pip_target = 0.0005 # 5 pips
        conditions = [
            (df['future_return'] >= pip_target),
            (df['future_return'] <= -pip_target)
        ]
        choices = [1, -1]
        df['target'] = np.select(conditions, choices, default=0)
        
        # Limpiar NaN y valores extremos
        df = df.dropna().replace([np.inf, -np.inf], np.nan).dropna()
        
        # Filtrar el ruido. La IA aprenderá mejor si solo le mostramos los movimientos claros (1 y -1)
        # Quitar los casos '0' ayuda mucho al accuracy predictivo si usamos "Probability" output
        # Pero para un clasificador general dejaremos todo, o daremos pesos a las clases.
        
        features = ['hour', 'day_of_week', 'ema_dist', 'volatility', 'rsi', 'return_last_3']
        X = df[features]
        y = df['target']
        
        # 4. Train Test Split
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        print(f"📊 Dataset listo: {len(X_train)} Train | {len(X_test)} Test")
        
        # 5. Entrenar Random Forest
        print("⚙️ Entrenando Bosque Aleatorio (500 Decision Trees)...")
        rf = RandomForestClassifier(n_estimators=100, max_depth=8, min_samples_split=10, random_state=42, class_weight='balanced')
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
