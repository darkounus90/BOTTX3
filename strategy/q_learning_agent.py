import json
import os
import numpy as np
import threading
from utils.logger import BotLogger

class QLearningAgent:
    """
    Agente Tabular de Q-Learning (Bajos Recursos)
    No usa PyTorch. Almacena en un diccionario (Estado -> Acción -> Q-Value).
    Aprende pasivamente sobre las señales de EMACross
    """
    
    FILE_PATH = "data/q_table.json"
    
    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.q_table = {}
        self.alpha = 0.1 # Tasa de aprendizaje
        self.gamma = 0.9 # Descuento de recompensas futuras
        self.epsilon = 0.05 # Muy bajo (solo interviene raramente en decisiones reales)
        self.lock = threading.Lock()
        self.load_table()

    def load_table(self):
        if os.path.exists(self.FILE_PATH):
            try:
                with open(self.FILE_PATH, 'r') as f:
                    self.q_table = json.load(f)
            except Exception as e:
                self.logger.error(f"Error cargando Q-Table: {e}")
        else:
            self.q_table = {}

    def save_table(self):
        with self.lock:
            try:
                os.makedirs('data', exist_ok=True)
                with open(self.FILE_PATH, 'w') as f:
                    json.dump(self.q_table, f, indent=4)
            except Exception as e:
                self.logger.error(f"Error guardando Q-Table: {e}")

    def _get_q(self, state, action):
        """Retorna el valor Q para el estado-acción (Por defecto 0 si es nuevo)"""
        s = str(state)
        a = str(action)
        if s not in self.q_table:
            self.q_table[s] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        return self.q_table[s].get(a, 0.0)

    def decide(self, state_tuple, base_recommendation):
        """
        Decide si seguir la estrategia base o intervenir (RL)
        state_tuple: ej. (EMA_Dist, RSI_Zone, ADX_Zone)
        """
        state_str = str(state_tuple)
        
        # Si no existe, inicializamos el estado con la recomendacion del bot Quant
        if state_str not in self.q_table:
            self.q_table[state_str] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
            
            # Le damos una pequeñísima ventaja a lo que la estrategia base sugiere
            # Para que el RL arranque guiado por el motor técnico
            if base_recommendation in self.q_table[state_str]:
                 self.q_table[state_str][base_recommendation] += 0.1
            
        # Exploración Epsilon-Greedy
        if np.random.rand() < self.epsilon:
            action = np.random.choice(['BUY', 'SELL', 'HOLD'])
            if action != base_recommendation:
                self.logger.info(f"🎲 RL Exploration: Interviniendo señal base ({base_recommendation}->{action})")
            return action
        else:
            # Explotar la mejor acción conocida o la recomendada si hay empate (0)
            qs = self.q_table[state_str]
            best_action = max(qs, key=qs.get)
            
            # Si todos son cero o no hay ventaja clara, seguimos al modelo base
            if qs[best_action] == 0.0:
                best_action = base_recommendation
                
            if best_action != base_recommendation:
                 self.logger.info(f"🧠 RL Exploitation: IA Matemáticas corrigieron la entrada a {best_action}")
                 
            return best_action

    def learn(self, state_tuple, action: str, reward: float, next_state_tuple):
        """
        Actualiza la tabla Q tras cerrar un trade.
        reward = Pips ganados o PnL del trade.
        """
        with self.lock:
            s = str(state_tuple)
            n_s = str(next_state_tuple)
            a = str(action)
            
            old_value = self._get_q(s, a)
            
            # Max Q value del siguiente estado
            if n_s not in self.q_table:
                self.q_table[n_s] = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
            
            next_max = max(self.q_table[n_s].values())
            
            # Formula de Bellman Q(s,a) = Q(s,a) + alpha * (R(s,a) + gamma * maxQ(s',a') - Q(s,a))
            new_value = old_value + self.alpha * (reward + self.gamma * next_max - old_value)
            
            self.q_table[s][a] = float(new_value)
            
            # Self-save no invasivo cada cierto aprendizaje
            if hash(s) % 10 == 0:
                self.save_table()
