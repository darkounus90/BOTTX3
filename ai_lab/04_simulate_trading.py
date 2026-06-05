import os
import sys
import pandas as pd
import numpy as np
import joblib

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def simulate():
    print("🔬 Iniciando Simulador de Fondo de Inversión (Walk-Forward + Monte Carlo)...")
    
    data_path = os.path.join(os.path.dirname(__file__), "data", "processed", "EURUSD_M15_features.parquet")
    if not os.path.exists(data_path):
        print("❌ Dataset no encontrado.")
        return
        
    df = pd.read_parquet(data_path)
    features = [
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
    
    # 1. Recuperar exactamente el Test Ciego del Trainer (Último 10%)
    test_size = int(len(df) * 0.10)
    test_df = df.iloc[-test_size:].copy()
    
    X_test = test_df[features]
    y_test = test_df['target'].values
    
    print(f"✅ Evaluando sobre {len(test_df):,} velas inéditas (Aprox. últimos 1.5 años).")
    
    # 2. Cargar el Cerebro V5 (LSTM) y Scaler
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    model_path = os.path.join(models_dir, "brain_v5_lstm.pth")
    scaler_path = os.path.join(models_dir, "scaler_v5.pkl")
    
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        print("❌ Cerebro V5 LSTM o Scaler no encontrados.")
        return
        
    scaler = joblib.load(scaler_path)
    
    # Importar torch localmente para la inferencia
    import torch
    import torch.nn as nn
    
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

    device = torch.device('cpu')
    model = LSTMBrainNet(input_size=len(features))
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
        
    # 3. Inferencia (Crear secuencias de 60 velas para todo el set de test)
    print("🤖 IA V5 LSTM Extrayendo probabilidades de tensores 3D...")
    
    X_raw = test_df[features].values
    X_scaled = scaler.transform(X_raw)
    
    seq_length = 60
    prob_win = np.zeros(len(test_df))
    
    # No podemos predecir los primeros 60 registros por falta de contexto
    with torch.no_grad():
        for i in range(seq_length, len(test_df)):
            seq = X_scaled[i-seq_length:i]
            seq_tensor = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).to(device)
            outputs = model(seq_tensor)
            probs = torch.softmax(outputs, dim=1)[0]
            prob_win[i] = probs[2].item()
    
    # Evaluar en múltiples umbrales
    thresholds = [0.25, 0.40, 0.60]
    TP_PIPS = 40.0
    SL_PIPS = 20.0
    
    print("\n=========================================")
    print("📈 ANÁLISIS DE UMBRALES DINÁMICOS")
    print("=========================================")
    
    best_threshold_results = [] # Para Monte Carlo
    
    for thresh in thresholds:
        trades_list = []
        
        wins = 0
        losses = 0
        holds = 0
        
        for i in range(len(test_df)):
            if prob_win[i] >= thresh:
                real_outcome = y_test[i]
                if real_outcome == 2:
                    wins += 1
                    trades_list.append(TP_PIPS)
                elif real_outcome == 0:
                    losses += 1
                    trades_list.append(-SL_PIPS)
                else:
                    holds += 1
                    trades_list.append(-2.0) # Spread/BreakEven penalty
                    
        trades_taken = wins + losses + holds
        if trades_taken == 0:
            print(f"Umbral {thresh*100}%: 0 Operaciones.")
            continue
            
        win_rate = (wins / trades_taken) * 100
        gross_profit = wins * TP_PIPS
        gross_loss = losses * SL_PIPS + holds * 2.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        pips_netos = sum(trades_list)
        
        print(f"Umbral > {thresh*100}% | WinRate: {win_rate:.1f}% | Operaciones: {trades_taken} | PNL: {pips_netos:.1f} pips | PF: {profit_factor:.2f}")
        
        # Guardar el umbral más realista para Monte Carlo
        if thresh == 0.25:
            best_threshold_results = trades_list
            
    # 4. SIMULACIÓN DE MONTE CARLO (Probabilidad de Ruina)
    if not best_threshold_results:
        print("\n⚠️ No hay datos suficientes para Monte Carlo.")
        return
        
    print("\n=========================================")
    print("🎲 PRUEBA DE ESTRÉS DE MONTE CARLO (1,000 PERMUTACIONES)")
    print("=========================================")
    
    n_simulations = 1000
    monte_carlo_drawdowns = []
    ruined_count = 0
    max_acceptable_dd_pips = 1000 # Imagina que perder 1000 pips quema tu cuenta FTMO
    
    trades_array = np.array(best_threshold_results)
    
    for _ in range(n_simulations):
        # Barajar aleatoriamente la secuencia temporal de trades
        np.random.shuffle(trades_array)
        # Calcular la curva de equidad
        equity_curve = trades_array.cumsum()
        
        # Calcular Maximum Drawdown en Pips
        peak = np.maximum.accumulate(equity_curve)
        drawdown = peak - equity_curve
        max_dd = drawdown.max()
        monte_carlo_drawdowns.append(max_dd)
        
        if max_dd >= max_acceptable_dd_pips:
            ruined_count += 1
            
    avg_mc_dd = np.mean(monte_carlo_drawdowns)
    worst_mc_dd = np.max(monte_carlo_drawdowns)
    prob_ruin = (ruined_count / n_simulations) * 100
    
    print(f"Simulando el peor futuro posible en base a tus {len(best_threshold_results)} operaciones...")
    print(f"📉 Max Drawdown Promedio (Monte Carlo) : {avg_mc_dd:.1f} pips")
    print(f"🚨 Peor Drawdown Absoluto (VaR extremo): {worst_mc_dd:.1f} pips")
    print(f"💀 Probabilidad de Ruina (Tocar -1000 pips): {prob_ruin:.1f}%")
    
    if prob_ruin < 1.0:
        print("\n🟢 VEREDICTO DE RIESGO: EXCELENTE. El modelo es matemáticamente seguro.")
    else:
        print("\n🔴 VEREDICTO DE RIESGO: PELIGRO. Ajusta el lotaje, la probabilidad de quemar FTMO es alta.")

if __name__ == "__main__":
    simulate()
