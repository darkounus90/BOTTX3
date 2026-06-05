import os
import sys
import pandas as pd
import numpy as np

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))

def calc_atr(df, period=14):
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - df['close'].shift()).abs()
    tr3 = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=1).mean()

def apply_triple_barrier(df, tp_pips=40, sl_pips=20, pip_size=0.0001, max_candles=40):
    print(f"🚦 Aplicando Método de Triple Barrera (TP: {tp_pips} pips, SL: {sl_pips} pips, Window: {max_candles})")
    
    close_prices = df['close'].values
    high_prices = df['high'].values
    low_prices = df['low'].values
    n = len(df)
    
    labels = np.ones(n, dtype=float) # 1 = Time expired (Ruido/Hold)
    
    tp_dist = tp_pips * pip_size
    sl_dist = sl_pips * pip_size
    
    for i in range(n - max_candles):
        entry = close_prices[i]
        tp_price = entry + tp_dist
        sl_price = entry - sl_dist
        
        for j in range(i + 1, i + max_candles + 1):
            hit_tp = high_prices[j] >= tp_price
            hit_sl = low_prices[j] <= sl_price
            
            if hit_sl and hit_tp:
                # Si en una misma vela toca ambos, por conservadurismo asumimos que tocó Stop Loss primero.
                labels[i] = 0
                break
            elif hit_sl:
                labels[i] = 0
                break
            elif hit_tp:
                labels[i] = 2
                break
                
    # Los últimos `max_candles` registros no pueden ser evaluados correctamente
    labels[-max_candles:] = np.nan
    return labels

def build_features():
    print("🧠 Iniciando Feature Engineering...")
    
    raw_path = os.path.join(os.path.dirname(__file__), "data", "raw", "EURUSD_M15.parquet")
    if not os.path.exists(raw_path):
        print("❌ Datos crudos no encontrados. Ejecuta 01_fetch_data.py primero.")
        return
        
    df = pd.read_parquet(raw_path)
    print(f"✅ Cargadas {len(df):,} velas históricas.")
    
    # --- FEATURES TEMPORALES ---
    df['hour'] = df['time'].dt.hour
    df['day_of_week'] = df['time'].dt.dayofweek
    
    # --- INDICADORES TÉCNICOS (V3 Institucional) ---
    PIP_SIZE = 0.0001
    
    # Medias Móviles y Distancias en Pips
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    
    df['dist_ema9_21_pips'] = (df['ema9'] - df['ema21']) / PIP_SIZE
    df['dist_close_ema50_pips'] = (df['close'] - df['ema50']) / PIP_SIZE
    df['dist_close_sma200_pips'] = (df['close'] - df['sma200']) / PIP_SIZE
    
    # Osciladores clásicos y StochRSI
    df['rsi14'] = calc_rsi(df['close'], 14)
    rsi_min = df['rsi14'].rolling(14).min()
    rsi_max = df['rsi14'].rolling(14).max()
    df['stoch_rsi'] = (df['rsi14'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    
    df['atr14_pips'] = calc_atr(df, 14) / PIP_SIZE
    
    # MACD normalizado en pips
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = (ema12 - ema26) / PIP_SIZE
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Bandas de Bollinger: Ancho (Volatilidad) y Z-Score (Posición)
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bbw'] = (std20 * 4) / sma20
    df['zscore20'] = (df['close'] - sma20) / (std20 + 1e-9)
    
    # Aceleración ROC (Rate of Change)
    df['roc_15'] = df['close'].pct_change(15) * 100
    df['roc_30'] = df['close'].pct_change(30) * 100
    
    # Momentum de velas en Pips
    df['return_1_pips'] = df['close'].diff(1) / PIP_SIZE
    df['return_3_pips'] = df['close'].diff(3) / PIP_SIZE
    df['return_5_pips'] = df['close'].diff(5) / PIP_SIZE
    
    # --- TARGET (TRIPLE BARRERA) ---
    df['target'] = apply_triple_barrier(df, tp_pips=40, sl_pips=20, pip_size=0.0001, max_candles=40)
    
    # Limpiar nulos generados por indicadores y triple barrera
    df = df.dropna().reset_index(drop=True)
    
    print(f"📊 Dataset final: {len(df):,} registros.")
    
    # Análisis de balanceo de clases
    print("\n⚖️ Balanceo de Etiquetas (0: Loss, 1: Hold, 2: Win):")
    counts = df['target'].value_counts(normalize=True) * 100
    for cls, pct in counts.items():
        print(f"   Clase {int(cls)}: {pct:.1f}%")
        
    # --- MUTUAL INFORMATION / CORRELACIÓN ---
    features = [c for c in df.columns if c not in ['time', 'open', 'high', 'low', 'close', 'target']]
    print("\n🔍 Analizando correlación de Pearson con el Target...")
    corr_matrix = df[features + ['target']].corr()
    target_corr = corr_matrix['target'].drop('target').abs().sort_values(ascending=False)
    
    print("Top 5 características predictivas:")
    print(target_corr.head(5))
    
    # Guardar Dataset de Entrenamiento
    output_dir = os.path.join(os.path.dirname(__file__), "data", "processed")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "EURUSD_M15_features.parquet")
    df.to_parquet(output_path, index=False, compression='snappy')
    print(f"\n💾 Dataset procesado guardado en: {output_path}")

if __name__ == "__main__":
    build_features()
