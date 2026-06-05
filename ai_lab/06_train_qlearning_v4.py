import os
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.tensorboard import SummaryWriter
import random

# Parámetros DRQN
GAMMA = 0.99
BATCH_SIZE = 128
LR = 0.0001
TARGET_UPDATE = 50
MEMORY_SIZE = 500000 
EPS_START = 1.0
EPS_END = 0.01
EPS_DECAY = 0.995

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ═══════════════════════════════════════════════════════════════
#  Dueling DRQN Architecture (Deep Recurrent Q-Network)
# ═══════════════════════════════════════════════════════════════
class DuelingDRQN(nn.Module):
    def __init__(self, input_size, hidden_size=128, num_actions=4):
        super(DuelingDRQN, self).__init__()
        
        # Cerebro Secuencial: Entiende el tiempo y el contexto
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=1, batch_first=True)
        
        # Flujo de Ventaja (Advantage Stream)
        self.advantage = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Linear(128, num_actions)
        )
        
        # Flujo de Valor (Value Stream)
        self.value = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )
        
    def forward(self, x):
        # x shape: (batch_size, seq_len=10, features=33)
        lstm_out, _ = self.lstm(x)
        
        # Extraemos la memoria del último instante de tiempo (la vela actual)
        last_out = lstm_out[:, -1, :] 
        
        adv = self.advantage(last_out)
        val = self.value(last_out)
        
        # Agregación: Q(s,a) = V(s) + (A(s,a) - mean(A))
        return val + adv - adv.mean(dim=1, keepdim=True)

# ═══════════════════════════════════════════════════════════════
#  Prioritized Experience Replay (SumTree)
# ═══════════════════════════════════════════════════════════════
class SumTree:
    def __init__(self, capacity):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)
        self.data = np.zeros(capacity, dtype=object)
        self.write = 0

    def _propagate(self, idx, change):
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx, s):
        left = 2 * idx + 1
        right = left + 1
        if left >= len(self.tree):
            return idx
        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self):
        return self.tree[0]

    def add(self, p, data):
        idx = self.write + self.capacity - 1
        self.data[self.write] = data
        self.update(idx, p)
        self.write += 1
        if self.write >= self.capacity:
            self.write = 0

    def update(self, idx, p):
        change = p - self.tree[idx]
        self.tree[idx] = p
        self._propagate(idx, change)

    def get(self, s):
        idx = self._retrieve(0, s)
        dataIdx = idx - self.capacity + 1
        return (idx, self.tree[idx], self.data[dataIdx])

class PrioritizedReplayMemory:
    def __init__(self, capacity, alpha=0.6, beta_start=0.4, beta_frames=100000):
        self.tree = SumTree(capacity)
        self.capacity = capacity
        self.alpha = alpha
        self.beta_start = beta_start
        self.beta_frames = beta_frames
        self.frame = 1
        self.epsilon = 0.01
        self.max_priority = 1.0
        self.size = 0
        
    def push(self, state, action, reward, next_state, done):
        transition = (state, action, reward, next_state, done)
        self.tree.add(self.max_priority ** self.alpha, transition)
        if self.size < self.capacity:
            self.size += 1
            
    def sample(self, batch_size):
        batch = []
        idxs = []
        priorities = []
        
        segment = self.tree.total() / batch_size
        beta = min(1.0, self.beta_start + self.frame * (1.0 - self.beta_start) / self.beta_frames)
        self.frame += 1
        
        for i in range(batch_size):
            a = segment * i
            b = segment * (i + 1)
            s = random.uniform(a, b)
            (idx, p, data) = self.tree.get(s)
            
            if data is not 0 and data is not None: 
                batch.append(data)
                idxs.append(idx)
                priorities.append(p)
                
        sampling_probabilities = np.array(priorities) / self.tree.total()
        is_weights = np.power(self.tree.capacity * sampling_probabilities, -beta)
        is_weights /= is_weights.max()
        
        return batch, idxs, is_weights
        
    def update_priorities(self, idxs, td_errors):
        for idx, err in zip(idxs, td_errors):
            p = (abs(err) + self.epsilon) ** self.alpha
            self.tree.update(idx, p)
            self.max_priority = max(self.max_priority, p)

    def __len__(self):
        return self.size

# ═══════════════════════════════════════════════════════════════
#  Trading Environment (Secuencial M15)
# ═══════════════════════════════════════════════════════════════
class TradingEnv:
    def __init__(self, df, window_size=10, initial_balance=50000.0):
        self.df = df
        self.window_size = window_size
        self.initial_balance = initial_balance
        
        drop_cols = ['time', 'target'] 
        existing_drop = [c for c in drop_cols if c in df.columns]
        clean_df = df.drop(columns=existing_drop).copy()
        clean_df.fillna(0, inplace=True)
        self.features = clean_df.values
        
        if 'close' in df.columns:
            self.closes = df['close'].values
        else:
            self.closes = self.features[:, 3]
            
        self.n_steps = len(df)
        self.reset()
        
    def reset(self):
        max_steps = 5000
        if self.n_steps > max_steps + self.window_size:
            self.current_step = random.randint(self.window_size, self.n_steps - max_steps - 1)
        else:
            self.current_step = self.window_size
            
        self.balance = self.initial_balance
        self.equity = self.initial_balance
        self.max_equity = self.initial_balance
        self.position = 0
        self.entry_price = 0.0
        return self._get_state()
        
    def _get_state(self):
        # 🔥 EL CAMBIO DE ORO: Retornamos matriz (10, 33) pura, sin aplanar.
        window = self.features[self.current_step - self.window_size : self.current_step]
        return window
        
    def step(self, action):
        current_price = self.closes[self.current_step]
        reward = 0.0
        lot_size = 100000 
        
        if action == 1: # BUY
            if self.position == -1:
                pnl = (self.entry_price - current_price) * lot_size
                self.balance += pnl
            if self.position != 1:
                self.position = 1
                self.entry_price = current_price
                reward -= 20.0 
                
        elif action == 2: # SELL
            if self.position == 1:
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            if self.position != -1:
                self.position = -1
                self.entry_price = current_price
                reward -= 20.0
                
        elif action == 3: # CLOSE
            if self.position == 1:
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            elif self.position == -1:
                pnl = (self.entry_price - current_price) * lot_size
                self.balance += pnl
            self.position = 0
            
        unrealized_pnl = 0.0
        if self.position == 1:
            unrealized_pnl = (current_price - self.entry_price) * lot_size
        elif self.position == -1:
            unrealized_pnl = (self.entry_price - current_price) * lot_size

        if action == 0 and self.position != 0:
            if unrealized_pnl > 0:
                reward += 2.0
            elif unrealized_pnl < 0:
                loss_magnitude = abs(unrealized_pnl) / 100.0
                reward -= (loss_magnitude ** 2)
            
        prev_equity = self.equity
        self.equity = self.balance + unrealized_pnl
        
        if self.equity > prev_equity:
            reward += 5.0
            
        if self.equity > self.max_equity:
            self.max_equity = self.equity
            reward += 100.0
            
        drawdown = (self.max_equity - self.equity) / self.max_equity
        done = False
        
        if drawdown >= 0.02:
            reward -= 200.0
            done = True
            
        self.current_step += 1
        
        if getattr(self, 'steps_in_episode', 0) >= 5000:
            done = True
        self.steps_in_episode = getattr(self, 'steps_in_episode', 0) + 1
            
        next_state = self._get_state() if not done else np.zeros_like(self._get_state())
        return next_state, reward, done

# ═══════════════════════════════════════════════════════════════
#  Training Loop
# ═══════════════════════════════════════════════════════════════
def train_dqn_v4():
    print("🚀 Iniciando Motor V4: Dueling DRQN (LSTM) + Ojos Institucionales + PER")
    
    data_path = os.path.join(os.path.dirname(__file__), "data", "processed", "EURUSD_M15_features.parquet")
    if not os.path.exists(data_path):
        print("❌ Archivo de features no encontrado.")
        return
        
    df = pd.read_parquet(data_path)
    df.dropna(inplace=True)
    
    env = TradingEnv(df, window_size=10, initial_balance=50000.0)
    
    # input_size = 33 características, seq_len = 10 velas
    seq_len, input_size = env._get_state().shape
    num_actions = 4
    
    print(f"🖥️ Dispositivo: {device} | 🧠 Matriz: {seq_len}x{input_size} (LSTM) | 🎮 Actions: {num_actions}")
    print(f"🌳 Generando Estructura SumTree Gigante...")
    
    writer = SummaryWriter(log_dir="runs/qlearning_v4")
    
    policy_net = DuelingDRQN(input_size, hidden_size=128, num_actions=num_actions).to(device)
    target_net = DuelingDRQN(input_size, hidden_size=128, num_actions=num_actions).to(device)
    target_net.load_state_dict(policy_net.state_dict())
    target_net.eval()
    
    optimizer = optim.AdamW(policy_net.parameters(), lr=LR, weight_decay=1e-4)
    memory = PrioritizedReplayMemory(MEMORY_SIZE)
    criterion = nn.SmoothL1Loss(reduction='none') 
    
    epsilon = EPS_START
    EPISODES = 200
    
    for episode in range(EPISODES):
        state_np = env.reset()
        env.steps_in_episode = 0
        state = torch.tensor(state_np, dtype=torch.float32, device=device).unsqueeze(0)
        
        total_reward = 0
        done = False
        
        while not done:
            if random.random() > epsilon:
                with torch.no_grad():
                    action = policy_net(state).max(1)[1].view(1, 1).item()
            else:
                action = random.randrange(num_actions)
                
            next_state_np, reward, done = env.step(action)
            total_reward += reward
            
            reward_t = torch.tensor([reward], device=device, dtype=torch.float32)
            next_state_t = torch.tensor(next_state_np, dtype=torch.float32, device=device).unsqueeze(0)
            action_t = torch.tensor([[action]], device=device, dtype=torch.long)
            done_t = torch.tensor([float(done)], device=device, dtype=torch.float32)
            
            memory.push(state, action_t, reward_t, next_state_t, done_t)
            state = next_state_t
            
            if len(memory) > BATCH_SIZE:
                transitions, idxs, is_weights = memory.sample(BATCH_SIZE)
                
                batch_state, batch_action, batch_reward, batch_next_state, batch_done = zip(*transitions)
                
                batch_state = torch.cat(batch_state)
                batch_action = torch.cat(batch_action)
                batch_reward = torch.cat(batch_reward)
                batch_next_state = torch.cat(batch_next_state)
                batch_done = torch.cat(batch_done)
                weights_t = torch.tensor(is_weights, dtype=torch.float32, device=device).unsqueeze(1)
                
                q_values = policy_net(batch_state).gather(1, batch_action)
                with torch.no_grad():
                    next_actions = policy_net(batch_next_state).max(1)[1].unsqueeze(1)
                    max_next_q_values = target_net(batch_next_state).gather(1, next_actions).detach().squeeze(1)
                    expected_q_values = batch_reward + (GAMMA * max_next_q_values * (1 - batch_done))
                    
                td_errors = (q_values - expected_q_values.unsqueeze(1)).squeeze(1)
                loss = (criterion(q_values, expected_q_values.unsqueeze(1)) * weights_t).mean()
                
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_value_(policy_net.parameters(), 100)
                optimizer.step()
                
                memory.update_priorities(idxs, td_errors.detach().cpu().numpy())
                
        epsilon = max(EPS_END, epsilon * EPS_DECAY)
        
        if episode % TARGET_UPDATE == 0:
            target_net.load_state_dict(policy_net.state_dict())
            
        writer.add_scalar('Métricas/Recompensa', total_reward, episode)
        writer.add_scalar('Métricas/Equity', env.equity, episode)
        writer.add_scalar('Métricas/Epsilon', epsilon, episode)
            
        print(f"👁️ V4 Episodio {episode+1:03d}/{EPISODES} | Reward: {total_reward:10.2f} | Epsilon: {epsilon:.3f} | Equity: ${env.equity:,.2f}", flush=True)
        
    writer.close()
    print("\n🔄 Exportando Agente AlphaGo V4 DRQN a formato ONNX...")
    dummy_input = torch.randn(1, seq_len, input_size, device=device)
    onnx_path = os.path.join(os.path.dirname(__file__), "models", "brain_qlearning_v4.onnx")
    os.makedirs(os.path.dirname(onnx_path), exist_ok=True)
    
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # ONNX Export for LSTM can be tricky. We set dynamic axes for batch size.
        torch.onnx.export(policy_net, dummy_input, onnx_path, 
                          input_names=['state'], output_names=['q_values'],
                          dynamic_axes={'state': {0: 'batch_size'}, 'q_values': {0: 'batch_size'}},
                          opset_version=14)
                          
    print(f"✅ ¡Cerebro V4 Dueling-DRQN (Con Ojos) exportado con éxito a {onnx_path}!")

if __name__ == "__main__":
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    train_dqn_v4()
