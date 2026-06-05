import os
import sys
import pandas as pd
import numpy as np
import joblib
import torch
import torch.nn as nn
import math
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

class PositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout=0.1, max_len=5000):
        super(PositionalEncoding, self).__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0) # (1, max_len, d_model)
        self.register_buffer('pe', pe)

    def forward(self, x):
        # x is (batch, seq_len, d_model)
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)

class BrainForgeV6Transformer(nn.Module):
    def __init__(self, input_size, d_model=64, nhead=4, num_layers=2, num_classes=3, dropout=0.5):
        super(BrainForgeV6Transformer, self).__init__()
        self.input_projection = nn.Linear(input_size, d_model)
        self.pos_encoder = PositionalEncoding(d_model, dropout)
        
        encoder_layers = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=d_model * 4,
            dropout=dropout, 
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=num_layers)
        
        self.fc_dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(d_model, num_classes)
        
    def forward(self, x):
        # x: (batch, seq_len, input_size)
        x = self.input_projection(x) # (batch, seq_len, d_model)
        x = self.pos_encoder(x)
        x = self.transformer_encoder(x) # (batch, seq_len, d_model)
        
        # Pooling: Tomamos la última vela de la secuencia como representación del estado
        x = x[:, -1, :] # (batch, d_model)
        
        x = self.fc_dropout(x)
        x = self.fc(x)
        return x

def create_sequences(data, targets, seq_length):
    xs = []
    ys = []
    for i in range(len(data) - seq_length):
        xs.append(data[i:(i + seq_length)])
        ys.append(targets[i + seq_length])
    return np.array(xs), np.array(ys)

def train_transformer_model():
    print("🧠 [BrainForge V6] Iniciando Entrenamiento Deep Learning (Transformer)...")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"🖥️ Dispositivo de Entrenamiento: {device}")
    
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'processed', 'EURUSD_M15_features.parquet')
    if not os.path.exists(data_path):
        print("❌ Dataset no encontrado. Ejecuta 02_build_features.py primero.")
        return
        
    df = pd.read_parquet(data_path)
    
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
    
    model = BrainForgeV6Transformer(
        input_size=len(features_list),
        d_model=64,
        nhead=4,
        num_layers=2,
        dropout=0.5
    ).to(device)
    
    # Class Imbalance Penalization
    class_weights = torch.tensor([1.0, 1.0, 1.5]).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    
    # Optimizer (AdamW recommended for Transformers) con lr microscópico
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0001, weight_decay=1e-3)
    
    EPOCHS = 50
    best_loss = float('inf')
    
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    model_path = os.path.join(models_dir, 'brain_v6_transformer.pth')
    
    print(f"🚀 Iniciando entrenamiento Transformer por {EPOCHS} Epochs...")
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
            
    # Load best model for ONNX export
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()
    
    print("🔄 Exportando modelo a formato ONNX para VPS (Alto Rendimiento)...")
    onnx_path = os.path.join(models_dir, 'brain_v6_transformer.onnx')
    
    # Dummy input for tracing
    dummy_input = torch.randn(1, SEQ_LENGTH, len(features_list)).to(device)
    
    torch.onnx.export(
        model, 
        dummy_input, 
        onnx_path, 
        export_params=True, 
        opset_version=14, 
        do_constant_folding=True, 
        input_names=['input'], 
        output_names=['output'],
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
    )
    print(f"✅ Modelo exportado exitosamente a ONNX: {onnx_path}")
            
    # Guardar scaler para uso en vivo
    scaler_path = os.path.join(models_dir, 'scaler_v6.pkl')
    joblib.dump(scaler, scaler_path)
    
    print(f"✅ Entrenamiento Completado.")
    print(f"💾 Scaler guardado en: {scaler_path}")

if __name__ == '__main__':
    train_transformer_model()
