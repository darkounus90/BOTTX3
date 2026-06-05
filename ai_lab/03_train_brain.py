import os
import sys
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import log_loss
from sklearn.model_selection import TimeSeriesSplit
import optuna
import joblib

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Global variables to prevent reloading in every trial
df = None
features = []

def load_data():
    global df, features
    data_path = os.path.join(os.path.dirname(__file__), "data", "processed", "EURUSD_M15_features.parquet")
    if not os.path.exists(data_path):
        print("❌ Dataset no encontrado. Ejecuta 02_build_features.py primero.")
        sys.exit(1)
        
    df = pd.read_parquet(data_path)
    exclude = ['time', 'open', 'high', 'low', 'close', 'target']
    features = [c for c in df.columns if c not in exclude]

def objective(trial):
    # Parametros de Búsqueda para XGBoost
    param = {
        "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=100),
        "max_depth": trial.suggest_int("max_depth", 3, 9),
        "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.05, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 7),
        "gamma": trial.suggest_float("gamma", 0.0, 2.0),
        "tree_method": "hist",
        "device": "cuda",
        "eval_metric": "mlogloss",
        "random_state": 42
    }
    
    # 3-Fold Walk-Forward Cross Validation
    tscv = TimeSeriesSplit(n_splits=3)
    
    X = df[features]
    y = df['target'].astype(int)
    
    scores = []
    
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        model = xgb.XGBClassifier(**param)
        model.fit(X_train, y_train, verbose=False)
        
        proba = model.predict_proba(X_val)
        # Log Loss multi-clase
        loss = log_loss(y_val, proba)
        scores.append(loss)
        
    return np.mean(scores)

def train_brain():
    global df
    print("🧠 Inicializando Motor V3 (Optuna + Walk-Forward)...")
    load_data()
    print(f"✅ Dataset cargado: {len(df):,} velas.")
    
    # Aislar el último 10% del dataset como Out-Of-Sample Ciego para el Simulador
    test_size = int(len(df) * 0.10)
    train_val_df = df.iloc[:-test_size]
    test_df = df.iloc[-test_size:]
    
    df = train_val_df # Optuna solo verá este sub-dataset
    
    print("\n🚀 Iniciando Fuerza Bruta de Optuna en RTX 5070...")
    N_TRIALS = 50  # Por defecto en demo, el usuario puede subirlo a 1000 en el script si desea dejarlo de noche
    print(f"   Ejecutando {N_TRIALS} Trials con 3-Fold Walk Forward Cross-Validation.")
    
    # Optuna study to MINIMIZE log_loss
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=True)
    
    print("\n🏆 Mejor Configuración Matemática Encontrada:")
    best_params = study.best_params
    for k, v in best_params.items():
        print(f"   {k}: {v}")
        
    print("\n🎓 Entrenando modelo maestro final con toda la historia...")
    best_params['tree_method'] = 'hist'
    best_params['device'] = 'cuda'
    best_params['random_state'] = 42
    
    final_model = xgb.XGBClassifier(**best_params)
    final_model.fit(train_val_df[features], train_val_df['target'].astype(int))
    
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(models_dir, exist_ok=True)
    
    model_path = os.path.join(models_dir, "brain_v3.pkl")
    joblib.dump(final_model, model_path)
    print(f"\n💾 CEREBRO V3 GUARDADO EN: {model_path}")

if __name__ == "__main__":
    train_brain()
