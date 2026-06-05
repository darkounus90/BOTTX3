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
    exclude = ['time', 'open', 'high', 'low', 'close', 'target']
    features = [c for c in df.columns if c not in exclude]
    
    # 1. Recuperar exactamente el Test Ciego del Trainer (Último 10%)
    test_size = int(len(df) * 0.10)
    test_df = df.iloc[-test_size:].copy()
    
    X_test = test_df[features]
    y_test = test_df['target'].values
    
    print(f"✅ Evaluando sobre {len(test_df):,} velas inéditas (Aprox. últimos 1.5 años).")
    
    # 2. Cargar el Cerebro V3
    model_path = os.path.join(os.path.dirname(__file__), "models", "brain_v3.pkl")
    if not os.path.exists(model_path):
        print("❌ Cerebro V3 no encontrado.")
        return
        
    model = joblib.load(model_path)
    try:
        model.set_params(device="cpu")
    except:
        pass
        
    # 3. Inferencia
    print("🤖 IA V3 Extrayendo probabilidades...")
    probs = model.predict_proba(X_test)
    prob_win = probs[:, 2] 
    
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
