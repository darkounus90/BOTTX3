import os
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from collections import deque
import random
import pygame

# Initialize Pygame selectively to avoid SDL bugs with Joysticks/Audio
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
pygame.display.init()
pygame.font.init()
WIDTH, HEIGHT = 1400, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("BrainForge V1 Q-Learning - AlphaGo Agent Visualizer")
clock = pygame.time.Clock()

# Colors
BG_COLOR = (15, 20, 25)
GREEN = (46, 204, 113)
RED = (231, 76, 60)
WHITE = (236, 240, 241)
GRAY = (149, 165, 166)
BLUE = (52, 152, 219)
YELLOW = (241, 196, 15)

font = pygame.font.SysFont("consolas", 18, bold=True)
large_font = pygame.font.SysFont("consolas", 24, bold=True)

# Parámetros DQN
GAMMA = 0.99
BATCH_SIZE = 128
LR = 0.0001
TARGET_UPDATE = 50
MEMORY_SIZE = 500000
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
        
        drop_cols = ['time', 'target'] 
        existing_drop = [c for c in drop_cols if c in df.columns]
        clean_df = df.drop(columns=existing_drop).copy()
        clean_df.fillna(0, inplace=True)
        self.features = clean_df.values
        
        self.closes = df['close'].values
        self.opens = df['open'].values
        self.highs = df['high'].values
        self.lows = df['low'].values
            
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
        self.steps_in_episode = 0
        self.action_history = {} # Para Pygame: marcar la acción en el gráfico
        
        return self._get_state()
        
    def _get_state(self):
        window = self.features[self.current_step - self.window_size : self.current_step]
        return window.flatten()
        
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
                reward -= 1.0
                
        elif action == 2: # SELL
            if self.position == 1:
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            if self.position != -1:
                self.position = -1
                self.entry_price = current_price
                reward -= 1.0
                
        elif action == 3: # CLOSE
            if self.position == 1:
                pnl = (current_price - self.entry_price) * lot_size
                self.balance += pnl
            elif self.position == -1:
                pnl = (self.entry_price - current_price) * lot_size
                self.balance += pnl
            self.position = 0
            
        if action in [1, 2]:
            self.action_history[self.current_step] = action
            
        unrealized_pnl = 0.0
        if self.position == 1:
            unrealized_pnl = (current_price - self.entry_price) * lot_size
        elif self.position == -1:
            unrealized_pnl = (self.entry_price - current_price) * lot_size
            
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
        self.steps_in_episode += 1
        
        if self.steps_in_episode >= 5000:
            done = True
            
        next_state = self._get_state() if not done else np.zeros_like(self._get_state())
        return next_state, reward, done

def draw_hud(screen, episode, total_reward, epsilon, env):
    pygame.draw.rect(screen, (25, 30, 40), (0, 0, WIDTH, 80))
    pygame.draw.line(screen, BLUE, (0, 80), (WIDTH, 80), 2)
    
    ep_txt = large_font.render(f"EPISODE: {episode:03d} / 200", True, WHITE)
    eq_color = GREEN if env.equity >= env.initial_balance else RED
    eq_txt = large_font.render(f"EQUITY: ${env.equity:,.2f}", True, eq_color)
    rew_color = GREEN if total_reward >= 0 else RED
    rew_txt = large_font.render(f"REWARD: {total_reward:,.2f}", True, rew_color)
    eps_txt = font.render(f"EPSILON: {epsilon:.3f}", True, YELLOW)
    pos_map = {0: "FLAT", 1: "LONG", -1: "SHORT"}
    pos_color = GRAY if env.position == 0 else (GREEN if env.position == 1 else RED)
    pos_txt = large_font.render(f"POS: {pos_map[env.position]}", True, pos_color)
    
    drawdown = (env.max_equity - env.equity) / env.max_equity * 100
    dd_txt = font.render(f"DRAWDOWN: {drawdown:.2f}%", True, RED if drawdown > 1.5 else WHITE)
    
    screen.blit(ep_txt, (20, 15))
    screen.blit(eq_txt, (350, 15))
    screen.blit(rew_txt, (700, 15))
    screen.blit(pos_txt, (1050, 15))
    
    screen.blit(eps_txt, (20, 50))
    screen.blit(dd_txt, (350, 50))

def draw_candles(screen, env):
    num_candles = 150
    start_idx = max(0, env.current_step - num_candles)
    end_idx = env.current_step
    
    if end_idx <= start_idx: return
    
    sub_opens = env.opens[start_idx:end_idx]
    sub_closes = env.closes[start_idx:end_idx]
    sub_highs = env.highs[start_idx:end_idx]
    sub_lows = env.lows[start_idx:end_idx]
    
    max_price = np.max(sub_highs)
    min_price = np.min(sub_lows)
    price_range = max_price - min_price
    if price_range == 0: price_range = 1e-9
    
    chart_y = 100
    chart_h = HEIGHT - 150
    candle_w = WIDTH / num_candles
    
    for i in range(len(sub_opens)):
        idx = start_idx + i
        x_center = i * candle_w + (candle_w / 2)
        
        o = chart_y + chart_h * (1 - (sub_opens[i] - min_price) / price_range)
        c = chart_y + chart_h * (1 - (sub_closes[i] - min_price) / price_range)
        h = chart_y + chart_h * (1 - (sub_highs[i] - min_price) / price_range)
        l = chart_y + chart_h * (1 - (sub_lows[i] - min_price) / price_range)
        
        color = GREEN if sub_closes[i] >= sub_opens[i] else RED
        
        pygame.draw.line(screen, color, (x_center, h), (x_center, l), 2)
        
        top = min(o, c)
        bottom = max(o, c)
        body_h = max(1, bottom - top)
        
        rect = pygame.Rect(x_center - (candle_w * 0.4), top, candle_w * 0.8, body_h)
        pygame.draw.rect(screen, color, rect)
        
        if idx in env.action_history:
            act = env.action_history[idx]
            if act == 1:
                pygame.draw.polygon(screen, GREEN, [
                    (x_center, l + 10), (x_center - 10, l + 25), (x_center + 10, l + 25)
                ])
            elif act == 2:
                pygame.draw.polygon(screen, RED, [
                    (x_center, h - 10), (x_center - 10, h - 25), (x_center + 10, h - 25)
                ])

def main():
    print("Levantando Motor de Videojuegos PyGame para Q-Learning...")
    data_path = os.path.join(os.path.dirname(__file__), "data", "processed", "EURUSD_M15_features.parquet")
    if not os.path.exists(data_path):
        print("❌ Dataset not found.")
        pygame.quit()
        return
        
    df = pd.read_parquet(data_path)
    env = TradingEnv(df, window_size=10, initial_balance=50000.0)
    input_size = env._get_state().shape[0]
    num_actions = 4
    
    policy_net = DQN(input_size, num_actions).to(device)
    target_net = DQN(input_size, num_actions).to(device)
    target_net.load_state_dict(policy_net.state_dict())
    
    optimizer = optim.AdamW(policy_net.parameters(), lr=LR, weight_decay=1e-4)
    memory = ReplayMemory(MEMORY_SIZE)
    criterion = nn.SmoothL1Loss()
    
    epsilon = EPS_START
    EPISODES = 200
    
    episode = 1
    state_np = env.reset()
    state = torch.tensor(state_np, dtype=torch.float32, device=device).unsqueeze(0)
    total_reward = 0
    
    running = True
    paused = False
    FPS = 120 # 120 velas por segundo = hiper-velocidad observable
    
    while running and episode <= EPISODES:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                if event.key == pygame.K_UP:
                    FPS = min(1000, FPS + 50)
                if event.key == pygame.K_DOWN:
                    FPS = max(10, FPS - 50)
                    
        if not paused:
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
                transitions = memory.sample(BATCH_SIZE)
                batch_state, batch_action, batch_reward, batch_next_state, batch_done = zip(*transitions)
                
                batch_state = torch.cat(batch_state)
                batch_action = torch.cat(batch_action)
                batch_reward = torch.cat(batch_reward)
                batch_next_state = torch.cat(batch_next_state)
                batch_done = torch.cat(batch_done)
                
                q_values = policy_net(batch_state).gather(1, batch_action)
                with torch.no_grad():
                    max_next_q_values = target_net(batch_next_state).max(1)[0].detach()
                    expected_q_values = batch_reward + (GAMMA * max_next_q_values * (1 - batch_done))
                    
                loss = criterion(q_values, expected_q_values.unsqueeze(1))
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_value_(policy_net.parameters(), 100)
                optimizer.step()
                
            if done:
                print(f"Episodio {episode} | Reward: {total_reward:.2f} | Eq: ${env.equity:.2f} | Epsilon: {epsilon:.3f}")
                epsilon = max(EPS_END, epsilon * EPS_DECAY)
                if episode % TARGET_UPDATE == 0:
                    target_net.load_state_dict(policy_net.state_dict())
                episode += 1
                state_np = env.reset()
                state = torch.tensor(state_np, dtype=torch.float32, device=device).unsqueeze(0)
                total_reward = 0

        screen.fill(BG_COLOR)
        draw_candles(screen, env)
        draw_hud(screen, episode, total_reward, epsilon, env)
        
        controls_txt = font.render(f"SPACE: Pause | UP/DOWN: Adjust Speed ({FPS} FPS)", True, GRAY)
        screen.blit(controls_txt, (20, HEIGHT - 30))
        
        pygame.display.flip()
        clock.tick(FPS)
        
    pygame.quit()

if __name__ == "__main__":
    main()
