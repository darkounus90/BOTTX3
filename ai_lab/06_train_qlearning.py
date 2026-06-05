import os
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
from collections import deque
import random

# Parámetros DQN
GAMMA = 0.99
BATCH_SIZE = 128
LR = 0.0001
TARGET_UPDATE = 50
MEMORY_SIZE = 500000 # Buffer gigante en VRAM
EPS_START = 1.0
EPS_END = 0.01
EPS_DECAY = 0.995

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class DQN(nn.Module):
    def __init__(self, input_size, num_actions):
        super(DQN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, 1024),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(1024, 512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Linear(256, num_actions)
        )
        
    def forward(self, x):
        return self.net(x)

class ReplayMemory:
    def __init__(self, capacity):
        self.memory = deque(maxlen=capacity)
        
    def push(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))
        
    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)
        
    def __len__(self):
        return len(self.memory)

class TradingEnv:
    def __init__(self, df, window_size=10, initial_balance=50000.0):
        self.df = df
        self.window_size = window_size
        self.initial_balance = initial_balance
        
        # Limpieza para alimentar la red solo con números puros
        drop_cols = ['time', 'target'] 
        existing_drop = [c for c in drop_cols if c in df.columns]
        clean_df = df.drop(columns=existing_drop).copy()
        
        # Rellenar cualquier NaNs para evitar colapsos en la matriz
        clean_df.fillna(0, inplace=True)
        self.features = clean_df.values
        
        # Aseguramos que tenemos acceso a la columna de precio
        if 'close' in df.columns:
            self.closes = df['close'].values
        else:
            self.closes = self.features[:, 3] # Asumimos close en la columna 3 si no se llama 'close'
            
        self.n_steps = len(df)
        self.reset()
        
    def reset(self):
        # Empezar en un punto aleatorio dejando espacio para un episodio de 5,000 velas
        max_steps = 5000
        if self.n_steps > max_steps + self.window_size:
            self.current_step = random.randint(self.window_size, self.n_steps - max_steps - 1)
        else:
            self.current_step = self.window_size
            
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.max_equity = self.initial_balance
        
        # Position: 0=None, 1=Long, -1=Short
        self.position = 0
        self.entry_price = 0.0
        
        return self._get_state()
        
    def _get_state(self):
        # Flatten the window of features (10 * 29)
        window = self.features[self.current_step - self.window_size : self.current_step]
        return window.flatten()
        
    def step(self, action):
        # Actions: 0=Hold, 1=Buy, 2=Sell, 3=Close
        current_price = self.closes[self.current_step]
        reward = 0.0
        
        # Tamaño de lote institucional simulado
        lot_size = 100000 
        
        # Execute action
        if action == 1: # BUY
            if self.position == -1: # Close short
                pnl = (self.entry_price - current_price) * lot_size
                self.balance += pnl
            if self.position != 1:
                self.position = 1
                self.entry_price = current_price
                reward -= 1.0 # Cost of spread/overtrading penalty
                
        elif action == 2: # SELL
            if self.position == 1: # Close long
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            if self.position != -1:
                self.position = -1
                self.entry_price = current_price
                reward -= 1.0 # Cost of spread/overtrading penalty
                
        elif action == 3: # CLOSE
            if self.position == 1:
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            elif self.position == -1:
                pnl = (self.entry_price - current_price) * lot_size
                self.balance += pnl
            self.position = 0
            
        # Calculate Equity
        unrealized_pnl = 0.0
        if self.position == 1:
            unrealized_pnl = (current_price - self.entry_price) * lot_size
        elif self.position == -1:
            unrealized_pnl = (self.entry_price - current_price) * lot_size
            
        prev_equity = self.equity
        self.equity = self.balance + unrealized_pnl
        
        # Rewards based on Equity
        if self.equity > prev_equity:
            reward += 5.0 # Recompensa por crecimiento
            
        if self.equity > self.max_equity:
            self.max_equity = self.equity
            reward += 100.0 # Recompensa Jackpot por nuevo ATH
            
        # Drawdown Penalty
        drawdown = (self.max_equity - self.equity) / self.max_equity
        done = False
        
        if drawdown >= 0.02: # 2% Drawdown (Límite FTMO simulado ajustado al episodio)
            reward -= 200.0 # Castigo Severo (Bancarrota)
            done = True
            
        self.current_step += 1
        
        # Límite de episodio para forzar a la red a ganar rápido
        if getattr(self, 'steps_in_episode', 0) >= 5000:
            done = True
        self.steps_in_episode = getattr(self, 'steps_in_episode', 0) + 1
            
        next_state = self._get_state() if not done else np.zeros_like(self._get_state())
        
        return next_state, reward, done

def train_dqn():
    print("🚀 Iniciando Motor de Reinforcement Learning (Q-Learning) V1")
    
    # Load processed data
    data_path = os.path.join(os.path.dirname(__file__), "data", "processed", "EURUSD_M15_features.parquet")
    if not os.path.exists(data_path):
        print("❌ Archivo de features no encontrado. Ejecutando canalización de datos...")
        return
        
    print(f"📥 Cargando entorno estacionario de 10 años: {data_path}")
    df = pd.read_parquet(data_path)
    
    # Escalar o limpiar features (Eliminamos NaN masivos si los hay en los extremos)
    df.dropna(inplace=True)
    
    env = TradingEnv(df, window_size=10, initial_balance=50000.0)
    input_size = env._get_state().shape[0]
    num_actions = 4
    
    print(f"🖥️ Dispositivo de Entrenamiento: {device}")
    print(f"🧠 Matriz de Estado (State Space): {input_size} features planas (10 velas)")
    print(f"🎮 Action Space: {num_actions} decisiones discretas")
    
    writer = SummaryWriter(log_dir="runs/qlearning_experiment_1")
    
    policy_net = DQN(input_size, num_actions).to(device)
    target_net = DQN(input_size, num_actions).to(device)
    target_net.load_state_dict(policy_net.state_dict())
    target_net.eval()
    
    optimizer = optim.AdamW(policy_net.parameters(), lr=LR, weight_decay=1e-4)
    memory = ReplayMemory(MEMORY_SIZE)
    criterion = nn.SmoothL1Loss() # Huber Loss es mejor para Q-Learning que MSE
    
    epsilon = EPS_START
    EPISODES = 200 # Partidas a jugar contra el mercado
    
    print(f"\n🎮 Arrancando Episodio 1... (Fuerza bruta con {EPISODES} partidas máximas)")
    
    for episode in range(EPISODES):
        state_np = env.reset()
        env.steps_in_episode = 0
        state = torch.tensor(state_np, dtype=torch.float32, device=device).unsqueeze(0)
        
        total_reward = 0
        done = False
        
        while not done:
            # Seleccionar Acción (Epsilon-Greedy)
            if random.random() > epsilon:
                with torch.no_grad():
                    action = policy_net(state).max(1)[1].view(1, 1).item()
            else:
                action = random.randrange(num_actions)
                
            # Ejecutar Acción en el Entorno
            next_state_np, reward, done = env.step(action)
            total_reward += reward
            
            # Convertir a Tensores
            reward_t = torch.tensor([reward], device=device, dtype=torch.float32)
            next_state_t = torch.tensor(next_state_np, dtype=torch.float32, device=device).unsqueeze(0)
            action_t = torch.tensor([[action]], device=device, dtype=torch.long)
            done_t = torch.tensor([float(done)], device=device, dtype=torch.float32)
            
            # Guardar en Experiencia
            memory.push(state, action_t, reward_t, next_state_t, done_t)
            state = next_state_t
            
            # Entrenamiento neuronal (Replay)
            if len(memory) > BATCH_SIZE:
                transitions = memory.sample(BATCH_SIZE)
                batch_state, batch_action, batch_reward, batch_next_state, batch_done = zip(*transitions)
                
                batch_state = torch.cat(batch_state)
                batch_action = torch.cat(batch_action)
                batch_reward = torch.cat(batch_reward)
                batch_next_state = torch.cat(batch_next_state)
                batch_done = torch.cat(batch_done)
                
                # Ecuación de Bellman
                q_values = policy_net(batch_state).gather(1, batch_action)
                with torch.no_grad():
                    max_next_q_values = target_net(batch_next_state).max(1)[0].detach()
                    expected_q_values = batch_reward + (GAMMA * max_next_q_values * (1 - batch_done))
                    
                loss = criterion(q_values, expected_q_values.unsqueeze(1))
                
                optimizer.zero_grad()
                loss.backward()
                # Clip de gradientes para estabilidad
                torch.nn.utils.clip_grad_value_(policy_net.parameters(), 100)
                optimizer.step()
                
        # Decaer exploración
        epsilon = max(EPS_END, epsilon * EPS_DECAY)
        
        # Actualizar Target Network periódicamente
        if episode % TARGET_UPDATE == 0:
            target_net.load_state_dict(policy_net.state_dict())
            
        # 📊 Escribir métricas en TensorBoard
        writer.add_scalar('Métricas/Recompensa', total_reward, episode)
        writer.add_scalar('Métricas/Equity', env.equity, episode)
        writer.add_scalar('Métricas/Epsilon', epsilon, episode)
            
        print(f"⚔️ Episodio {episode+1:03d}/{EPISODES} | Recompensa Acumulada: {total_reward:10.2f} | Epsilon: {epsilon:.3f} | Equity Final: ${env.equity:,.2f}", flush=True)
        
    writer.close()
    print("\n🔄 Exportando Agente AlphaGo a formato ONNX...")
    dummy_input = torch.randn(1, input_size, device=device)
    onnx_path = os.path.join(os.path.dirname(__file__), "models", "brain_qlearning_v1.onnx")
    os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
    
    # Manejar deprecaciones limpiamente
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        torch.onnx.export(policy_net, dummy_input, onnx_path, 
                          input_names=['state'], output_names=['q_values'],
                          opset_version=14)
                          
    print(f"✅ ¡Cerebro Q-Learning exportado con éxito a {onnx_path}!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    train_dqn()
