import sys
import os
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Adjust path to import core correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import BotConfig
from core.llm_oracle import GeminiOracle
from utils.logger import BotLogger

def find_failed_zscore_trades(symbol="GBPUSD", days=60):
    if not mt5.initialize():
        print("❌ Error: MT5 Not initialized")
        return []
        
    print(f"[*] Escaneando el historial de {days} días buscando los perdedores del Z-Score...")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days * 24 * 4)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['std_50'] = df['close'].rolling(window=50).std()
    df['z_score'] = (df['close'] - df['sma_50']) / (df['std_50'] + 1e-9)
    df['tr'] = df['high'] - df['low']
    df['atr'] = df['tr'].rolling(14).mean()
    
    z_threshold = 2.5
    failed_trades = []
    
    for i in range(250, len(df) - 50):
        prev = df.iloc[i-1]
        curr = df.iloc[i]
        signal = None
        
        if prev['z_score'] >= z_threshold and curr['z_score'] < z_threshold and curr['close'] < curr['ema_200']:
            signal = "SELL"
        elif prev['z_score'] <= -z_threshold and curr['z_score'] > -z_threshold and curr['close'] > curr['ema_200']:
            signal = "BUY"
            
        if not signal: continue
        
        # Simular si falla
        sl_pips = round((curr['atr'] * 1.5) / 0.0001, 1)
        tp_pips = round((curr['atr'] * 2.5) / 0.0001, 1)
        
        entry = curr['close']
        sl_price = entry - (sl_pips*0.0001) if signal == "BUY" else entry + (sl_pips*0.0001)
        tp_price = entry + (tp_pips*0.0001) if signal == "BUY" else entry - (tp_pips*0.0001)
        
        failed = False
        future = df.iloc[i+1:i+30]
        for _, row in future.iterrows():
            if signal == "BUY":
                if row['low'] <= sl_price: failed = True; break
                if row['high'] >= tp_price: break
            else:
                if row['high'] >= sl_price: failed = True; break
                if row['low'] <= tp_price: break
                
        if failed:
            failed_trades.append({
                "time": curr['time'],
                "signal": signal,
                "entry": entry,
                "z_score": curr['z_score'],
                "sl_pips": sl_pips
            })
            if len(failed_trades) >= 3:
                break
                
    mt5.shutdown()
    return failed_trades

def run_autopsy():
    logger = BotLogger("TradeAutopsy")
    oracle = GeminiOracle(logger)
    
    print("\n" + "="*80)
    print("💀 INICIANDO AUTOPSIA DE IA FORENSE SOBRE TRADES FALLIDOS (GBPUSD)")
    print("="*80)
    
    trades = find_failed_zscore_trades("GBPUSD", 60)
    if not trades:
        print("✅ Increíble: No se encontraron trades fallidos recientes. ¡Estrategia rozando la perfección matemática!")
        return
        
    print(f"\n[!] Se han extraído {len(trades)} cadáveres financieros del historial para análisis forense.\n")
        
    for idx, t in enumerate(trades):
        print(f"[{idx+1}] Analizando Trade Matemático Fallido:")
        print(f"🔸 Fecha de Muerte: {t['time']}")
        print(f"🔸 Dirección Quant: {t['signal']} @ {t['entry']:.5f} (Stop Loss: {t['sl_pips']} pips)")
        print(f"🔸 Razón Quant: Z-Score de {t['z_score']:.2f} (Anomalía Severa)")
        print("-" * 50)
        print("🧠 Consultando al CIO (Gemini) sobre este error estructural...\n")
        
        prompt = (
            f"ERES EL CIO AUDITOR DE UN HEDGE FUND QUANT.\n"
            f"Símbolo: GBPUSD | Fecha del error: {t['time']} | Señal: {t['signal']} a precio {t['entry']:.5f}\n"
            f"Este trade fue disparado por nuestro Bot algorítmico porque el precio alcanzó un Z-Score de {t['z_score']:.2f} (sobreextensión brutal de la media) pero resultó ser una TRAMPA y nos cazó el Stop Loss.\n\n"
            f"Sabiendo que operamos M15 con Smart Money Concepts, analiza teóricamente por qué un sistema de Reversión a la media fallaría bajo esta anomalía y continuaría rompiendo estructura (¿Macro fundamental? ¿Cacería de liquidez institucional? ¿Hora de Londres/NY?).\n"
            f"Concluye diciendo explícitamente: 'DICTAMEN: RECHAZADO' y explica qué filtro hubieras usado para evitar tomar este trade basándote en la fecha/hora y liquidez de FX."
        )
        
        resp = oracle.ask_oracle(prompt)
        print(f"✨ RESULTADO FORENSE:\n{resp}\n")
        print("="*80 + "\n")
        
if __name__ == '__main__':
    run_autopsy()
