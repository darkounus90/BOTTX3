import os
import sys
import pandas as pd
import numpy as np
import joblib
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

class ForexDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)
        
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

class LSTMBrainNet(nn.Module):
    def __init__(self, input_size, hidden_size=32, num_layers=1, num_classes=3, dropout=0.5):
        super(LSTMBrainNet, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # Reducción drástica de neuronas y capas para evitar memorización
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, 
                            batch_first=True, dropout=dropout if num_layers > 1 else 0)
        
        # Dropout gigante del 50% para matar neuronas aleatoriamente y forzar generalización
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

def create_sequences(data, targets, seq_length):
    xs = []
    ys = []
    for i in range(len(data) - seq_length):
        xs.append(data[i:(i + seq_length)])
        ys.append(targets[i + seq_length])
    return np.array(xs), np.array(ys)

def train_dl_model():
    print("🧠 [BrainForge V5] Iniciando Entrenamiento Deep Learning (LSTM)...")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"🖥️ Dispositivo de Entrenamiento: {device}")
    
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'EURUSD_M15_features.parquet')
    if not os.path.exists(data_path):
        print("❌ Dataset no encontrado. Ejecuta 02_build_features.py primero.")
        return
        
    df = pd.read_parquet(data_path)
    
    # Exclusivamente features ESTACIONARIAS (Sin precios absolutos)
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
    
    X_raw = df[features_list].values
    y_raw = df['target'].values
    
    print(f"📊 Escalando {len(X_raw)} filas...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_raw)
    
    SEQ_LENGTH = 60 # 15 horas de contexto histórico
    print(f"🔄 Generando tensores 3D con ventanas de {SEQ_LENGTH} velas...")
    X_seq, y_seq = create_sequences(X_scaled, y_raw, SEQ_LENGTH)
    
    X_train, X_val, y_train, y_val = train_test_split(X_seq, y_seq, test_size=0.2, shuffle=False)
    
    train_dataset = ForexDataset(X_train, y_train)
    val_dataset = ForexDataset(X_val, y_val)
    
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=256, shuffle=False)
    
    model = LSTMBrainNet(input_size=len(features_list)).to(device)
    
    # Ponderación de pesos (Class Imbalance Penalization)
    class_weights = torch.tensor([1.0, 1.0, 1.5]).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    
    # Weight Decay pesado para castigar sobreajuste (Regularización L2)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    
    EPOCHS = 50
    best_loss = float('inf')
    
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, 'brain_v5_lstm.pth')
    
    print(f"🚀 Iniciando entrenamiento por {EPOCHS} Epochs...")
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        correct = 0
        total = 0
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                val_loss += loss.item()
                
                _, predicted = torch.max(outputs.data, 1)
                total += batch_y.size(0)
                correct += (predicted == batch_y).sum().item()
                
        val_acc = 100 * correct / total
        avg_val_loss = val_loss / len(val_loader)
        
        print(f"Epoch [{epoch+1}/{EPOCHS}] | Train Loss: {train_loss/len(train_loader):.4f} | Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:.2f}%")
        
        if avg_val_loss < best_loss:
            best_loss = avg_val_loss
            torch.save(model.state_dict(), model_path)
            
    # Guardar scaler para uso en vivo
    scaler_path = os.path.join(models_dir, 'scaler_v5.pkl')
    joblib.dump(scaler, scaler_path)
    
    print(f"✅ Entrenamiento Completado.")
    print(f"💾 Modelo LSTM V5 guardado en: {model_path}")
    print(f"💾 Scaler guardado en: {scaler_path}")

if __name__ == '__main__':
    train_dl_model()
