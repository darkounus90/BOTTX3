import sys
import os
import MetaTrader5 as mt5
import pandas as pd
import json
from datetime import datetime

# Paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from strategy.q_learning_agent import QLearningAgent
from utils.logger import BotLogger
from config.settings import BotConfig

class MLTrainerQLearning:
    def __init__(self, timeframe=mt5.TIMEFRAME_M5, bars=50000):
        self.watchlist = BotConfig.WATCHLIST
        self.timeframe = timeframe
        self.bars = bars
        self.logger = BotLogger("Q-Train")
        self.q_agent = QLearningAgent(self.logger)
        
        # Hyperparameters for simulation
        self.sl_pips = 20
        self.tp_pips = 40
        self.pip_size = 0.0001
        
    def run(self):
        self.logger.banner(f"🧠 SIMULADOR HISTÓRICO Q-LEARNING MULTI-PAR")
        
        if not mt5.initialize():
            self.logger.error("❌ MT5 Error de conexión. Abre la terminal MetaTrader en este PC.")
            return

        total_trades_executed = 0
        total_wins = 0
        total_losses = 0

        for target_symbol in self.watchlist:
            self.logger.info(f"==> 📥 Intentando preparar histórico para {target_symbol}...")
            
            df = None
            
            # --- 1. FALLBACK A CSV LOCAL (Para saltar bloqueos del broker) ---
            import os
            csv_path = os.path.join("data", f"{target_symbol}_M5.csv")
            if os.path.exists(csv_path):
                self.logger.success(f"📂 ¡Encontrado archivo local '{csv_path}'! Saltando bloqueo del API MT5...")
                try:
                    df_raw = pd.read_csv(csv_path, sep=None, engine='python')
                    
                    # Limpiar nombres de columnas si vienen con espacios extra
                    df_raw.rename(columns=lambda x: x.strip(), inplace=True)
                    
                    # Formato nativo de exportación MT5
                    if '<DATE>' in df_raw.columns and '<TIME>' in df_raw.columns:
                        df_raw['time'] = pd.to_datetime(df_raw['<DATE>'] + ' ' + df_raw['<TIME>'], format='%Y.%m.%d %H:%M:%S', errors='coerce')
                        df_raw.rename(columns={'<OPEN>': 'open', '<HIGH>': 'high', '<LOW>': 'low', '<CLOSE>': 'close'}, inplace=True)
                    elif 'time' not in df_raw.columns:
                        self.logger.error("❌ El CSV no tiene el formato esperado de MT5.")
                        df_raw = None
                        
                    if df_raw is not None:
                        df = df_raw.dropna(subset=['time', 'close', 'open', 'high', 'low']).copy()
                        self.logger.success(f"✅ {len(df)} velas cargadas desde archivo local.")
                except Exception as e:
                    self.logger.error(f"❌ Error leyendo {csv_path}: {e}")

            # --- 2. DESCARGA VÍA API (Se bloquea de noche) ---
            if df is None:
                actual_symbol = target_symbol
                mt5.symbol_select(actual_symbol, True)
                now = datetime.now()
                rates = mt5.copy_rates_from(actual_symbol, self.timeframe, now, self.bars)
            
            # Si la descarga inicial falla, buscar un alias válido (ej: EURUSD.pro)
            if rates is None or len(rates) == 0:
                self.logger.warning(f"⚠️ Descarga directa fallida para {target_symbol}. Escaneando diccionarios MT5...")
                symbols = mt5.symbols_get()
                if symbols:
                    for s in symbols:
                        if target_symbol.upper() in s.name.upper() and s.name.upper() != target_symbol.upper():
                            # Probar si el broker permite descargar datos en este alias
                            mt5.symbol_select(s.name, True)
                            test_rates = mt5.copy_rates_from(s.name, self.timeframe, now, 10)
                            if test_rates is not None and len(test_rates) > 0:
                                actual_symbol = s.name
                                self.logger.success(f"🔍 Alias corporativo funcional hallado: {actual_symbol}")
                                break
                                
                # Reintentar la descarga larga con el nuevo alias
                mt5.symbol_select(actual_symbol, True)
                rates = mt5.copy_rates_from(actual_symbol, self.timeframe, now, self.bars)
            
            # Fallback a menos velas si el broker no tiene tanta historia guardada
            if rates is None or len(rates) == 0:
                error_code = mt5.last_error()
                self.logger.warning(f"⚠️ El broker bloqueó excesivos datos [Código: {error_code}]. Intentando con 5000 velas...")
                mt5.symbol_select(actual_symbol, True)
                rates = mt5.copy_rates_from(actual_symbol, self.timeframe, now, 5000)
                
                if rates is None or len(rates) == 0:
                    error_code = mt5.last_error()
                    self.logger.error(f"❌ Fallo definitivo en {actual_symbol}, Código MT5: {error_code}.")
                    symbols = mt5.symbols_get()
                    if symbols:
                        posibles = [s.name for s in symbols if target_symbol[:3].upper() in s.name.upper()]
                        self.logger.info(f"💡 El broker podría estar escondiendo el símbolo bajo estos nombres:")
                        for idx, p in enumerate(posibles[:5]):
                            self.logger.info(f"   -> {p}")
                    continue
    
                self.logger.success(f"✅ {len(rates)} velas descargadas correctamente vía API de {actual_symbol}.")
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Formateado de Datos y Cálculo de Indicadores Técnicos Clave
            df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            
            # Bucle de Simulación de Trades (Time Machine)
            self.logger.info(f"🚀 Iniciando Simulación Acelerada para {actual_symbol}...")
            
            # Determinar tamaño del pip para divisas con JPY
            current_pip_size = 0.01 if "JPY" in actual_symbol else 0.0001
            
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
                    total_trades_executed += 1
                    if reward == 1: total_wins += 1
                    if reward == -1: total_losses += 1
                    
                    # Llamar al algoritmo literal de Bellman
                    # Inyectar también el nombre del par en el estado puede ayudar a diferenciar comportamientos
                    estado_fotografia_par = (actual_symbol, hour_of_day, candle_color)
                    self.q_agent.learn(estado_fotografia_par, signal, reward, estado_fotografia_par)

        mt5.shutdown()
        self.q_agent.save_table()
        
        self.logger.success(f"✅ ENTRENAMIENTO MULTI-PAR COMPLETADO.")
        self.logger.info(f"📊 Trades Totales Simulados: {total_trades_executed}")
        self.logger.info(f"🏆 Wins: {total_wins} | 💥 Losses: {total_losses} (Anotados en Q-Table)")
        self.logger.success(f"💾 Memoria de Experiencia Q guardada. Bot Listo.")

if __name__ == "__main__":
    trainer = MLTrainerQLearning()
    trainer.run()
