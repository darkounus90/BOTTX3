import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import json

# Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from strategy.q_learning_agent import QLearningAgent
from utils.logger import BotLogger

class MLTrainerQLearning:
    def __init__(self, symbol="EURUSD", timeframe=mt5.TIMEFRAME_M5, bars=50000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.bars = bars
        self.logger = BotLogger("Q-Train")
        self.q_agent = QLearningAgent(self.logger)
        
        # Hyperparameters for simulation
        self.sl_pips = 20
        self.tp_pips = 40
        self.pip_size = 0.0001
        
    def run(self):
        self.logger.banner(f"🧠 SIMULADOR HISTÓRICO Q-LEARNING ({self.symbol})")
        
        if not mt5.initialize():
            self.logger.error("❌ MT5 Error de conexión. Abre la terminal MetaTrader en este PC.")
            return
            
        self.logger.info(f"📥 Buscando símbolo compatible para {self.symbol}...")
        
        # Auto-detect broker suffix (e.g., EURUSD.pro, EURUSD.a)
        actual_symbol = self.symbol
        symbols = mt5.symbols_get()
        if symbols:
            for s in symbols:
                if self.symbol in s.name:
                    actual_symbol = s.name
                    break
        
        self.logger.info(f"📥 Descargando {self.bars} velas históricas para {actual_symbol}...")
        rates = mt5.copy_rates_from_pos(actual_symbol, self.timeframe, 0, self.bars)
        
        # Fallback a menos velas si el broker no tiene tanta historia guardada
        if rates is None or len(rates) == 0:
            self.logger.warning(f"⚠️ El broker bloqueó {self.bars} velas. Intentando con 5000...")
            rates = mt5.copy_rates_from_pos(actual_symbol, self.timeframe, 0, 5000)
            
        if rates is None or len(rates) == 0:
            self.logger.error(f"❌ No hay datos descargados para {actual_symbol}. Revisa si tu broker permite descargas históricas.")
            mt5.shutdown()
            return

        self.logger.success(f"✅ {len(rates)} velas descargadas correctamente de {actual_symbol}.")
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calcular Indicadores Técnicos Clave para el Agente
        self.logger.info("⚙️ Calculando indicadores vectoriales...")
        df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
        
        # Bucle de Simulación de Trades (Time Machine)
        self.logger.info("🚀 Iniciando Simulación Acelerada (Jugando 5 años de Trades en 10 segundos)...")
        trades_executed = 0
        wins = 0
        losses = 0
        
        for i in range(50, len(df) - 50): # Dejar espacio futuro para ver resultados
            current = df.iloc[i]
            prev = df.iloc[i-1]
            
            # 1. Estrategia Base: Cruce Simple (Simulamos lo que haría el bot quant)
            signal = "HOLD"
            if prev['ema9'] < prev['ema21'] and current['ema9'] > current['ema21']:
                signal = "BUY"
            elif prev['ema9'] > prev['ema21'] and current['ema9'] < current['ema21']:
                signal = "SELL"
                
            if signal != "HOLD":
                # Fabricar Estado (Fotografía)
                # Ejemplo de estado simple: Hora del día, y si la vela fue alcista/bajista
                hour_of_day = int(current['time'].hour)
                candle_color = "GREEN" if current['close'] > current['open'] else "RED"
                estado_fotografia = (hour_of_day, candle_color)
                
                # Vamos al futuro para ver si habría ganado o perdido (SL o TP hit)
                entry_price = current['close']
                reward = 0
                
                if signal == "BUY":
                    for j in range(i+1, min(i+100, len(df))): # Buscar en las siguientes 100 velas
                        fut = df.iloc[j]
                        if fut['low'] <= entry_price - (self.sl_pips * self.pip_size):
                            reward = -1 # Hit Stop Loss
                            break
                        elif fut['high'] >= entry_price + (self.tp_pips * self.pip_size):
                            reward = 1  # Hit Take Profit
                            break
                elif signal == "SELL":
                    for j in range(i+1, min(i+100, len(df))):
                        fut = df.iloc[j]
                        if fut['high'] >= entry_price + (self.sl_pips * self.pip_size):
                            reward = -1 # Hit Stop Loss
                            break
                        elif fut['low'] <= entry_price - (self.tp_pips * self.pip_size):
                            reward = 1  # Hit Take Profit
                            break
                            
                # Aprender del resultado (Castigo o Premio)
                if reward != 0:
                    trades_executed += 1
                    if reward == 1: wins += 1
                    if reward == -1: losses += 1
                    
                    # Llamar al algoritmo literal de Bellman
                    # El próximo estado no importa tanto para trades episódicos aislados, usamos None o el mismo
                    self.q_agent.learn(estado_fotografia, signal, reward, estado_fotografia)

        mt5.shutdown()
        self.q_agent.save_table()
        
        self.logger.success(f"✅ ENTRENAMIENTO COMPLETADO.")
        self.logger.info(f"📊 Trades Simulados Históricamente: {trades_executed}")
        self.logger.info(f"🏆 Wins: {wins} | 💥 Losses: {losses} (Anotados en Q-Table)")
        self.logger.success(f"💾 Memoria de Experiencia Q guardada. Bot listo para operar.")

if __name__ == "__main__":
    trainer = MLTrainerQLearning()
    trainer.run()
