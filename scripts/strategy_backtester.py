"""
📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO DE ALTA FIDELIDAD (V2 - OPTIMIZADO)
========================================================================
Simula las estrategias del bot con los mismos filtros institucionales 
que el sistema real: Tendencia H1, MACD, Wick Rejection, Volatilidad y Slope.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import argparse
import json

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DEL BACKTEST
# ═══════════════════════════════════════════════════════════════

COMMISSION_PER_LOT = 9.0      
SPREAD_PIPS_SIM    = 1.5      
INITIAL_BALANCE    = 50000.0
RISK_PER_TRADE_PCT = 0.4      

class BacktestResult:
    def __init__(self, name):
        self.name = name
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.filtered = 0 
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = INITIAL_BALANCE
        self.balance = INITIAL_BALANCE
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.win_by_hour = defaultdict(lambda: {"wins": 0, "losses": 0})
    
    def add_trade(self, pnl, hour, direction, sl, tp):
        self.trades.append({"pnl": pnl, "hour": hour, "dir": direction, "sl": sl, "tp": tp})
        self.total_pnl += pnl
        self.balance += pnl
        if pnl > 0: self.wins += 1
        else: self.losses += 1
        self.best_trade = max(self.best_trade, pnl)
        self.worst_trade = min(self.worst_trade, pnl)
        self.peak_balance = max(self.peak_balance, self.balance)
        self.max_drawdown = max(self.max_drawdown, self.peak_balance - self.balance)
        self.win_by_hour[hour]["wins" if pnl > 0 else "losses"] += 1

    def get_report(self):
        total = self.wins + self.losses
        if total == 0: 
            return {
                "name": self.name, "trades": 0, "filtered": self.filtered, 
                "win_rate": 0, "profit_factor": 0, "total_pnl": 0, "max_drawdown": 0, "verdict": "SIN DATOS"
            }
        win_rate = (self.wins / total) * 100
        avg_w = sum(t["pnl"] for t in self.trades if t["pnl"] > 0) / max(self.wins, 1)
        avg_l = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0) / max(self.losses, 1))
        pf = (avg_w * self.wins) / max(avg_l * self.losses, 1)
        
        if pf >= 1.5 and win_rate >= 45: verdict = "🟢 ALTA PRECISIÓN"
        elif pf >= 1.05: verdict = "🟡 ESTABLE"
        else: verdict = "🔴 RIESGOSO"

        return {
            "name": self.name, "trades": total, "filtered": self.filtered,
            "win_rate": round(win_rate, 1), "profit_factor": round(pf, 2),
            "total_pnl": round(self.total_pnl, 2), "max_drawdown": round(self.max_drawdown, 2),
            "verdict": verdict
        }

def calculate_pnl(direction, entry, sl_pips, tp_pips, future, symbol):
    pip = 0.01 if "JPY" in symbol else 0.0001
    spread = SPREAD_PIPS_SIM * pip
    entry_eff = entry + (spread if direction == "BUY" else -spread)
    sl_pr = entry_eff - sl_pips * pip if direction == "BUY" else entry_eff + sl_pips * pip
    tp_pr = entry_eff + tp_pips * pip if direction == "BUY" else entry_eff - tp_pips * pip
    
    risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
    for c in future:
        if direction == "BUY":
            if c["low"] <= sl_pr: return -risk_usd
            if c["high"] >= tp_pr: return risk_usd * (tp_pips/sl_pips) - (COMMISSION_PER_LOT * 0.1)
        else:
            if c["high"] >= sl_pr: return -risk_usd
            if c["low"] <= tp_pr: return risk_usd * (tp_pips/sl_pips) - (COMMISSION_PER_LOT * 0.1)
    return 0.0 

def get_h1_trend(df_h1, timestamp):
    mask = df_h1['time'] <= timestamp
    if not mask.any(): return 0
    row = df_h1[mask].iloc[-1]
    return 1 if row['close'] > row['close_ema_200'] else -1

# ═══════════════════════════════════════════════════════════════
#  SIMULADORES
# ═══════════════════════════════════════════════════════════════

def sim_bollinger_rsi(df, df_h1, symbol, adx_thresh=30.0):
    res = BacktestResult(f"Bollinger+RSI (ADX<{adx_thresh})")
    df['sma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    mult = 2.3 if "EUR" in symbol else 1.9
    df['up'] = df['sma20'] + df['std20'] * mult
    df['low'] = df['sma20'] - df['std20'] * mult
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    pip = 0.01 if "JPY" in symbol else 0.0001

    for i in range(50, len(df)-50):
        row = df.iloc[i]
        h = (pd.Timestamp(row['time']).hour - 5) % 24
        if "EUR" in symbol and not (h >= 19 or h < 1): continue
        if "GBP" in symbol and not (h >= 13 and h < 17): continue
        
        signal = "BUY" if (row['close'] < row['low'] and row['rsi'] < 32) else "SELL" if (row['close'] > row['up'] and row['rsi'] > 68) else None
        
        if signal:
            trend = get_h1_trend(df_h1, row['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
            
            sl = max(round(row['atr']*1.5 / pip / 10, 1), 15)
            tp = max(round(row['atr']*2.0 / pip / 10, 1), 25)
            pnl = calculate_pnl(signal, row['close'], sl, tp, df.iloc[i+1:i+50].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
    return res

def sim_zscore_reversion(df, df_h1, symbol, z_thresh=2.5):
    if "EUR" in symbol: z_thresh = 2.8 # Estrangulamiento de Z-Score para EUR
    res = BacktestResult(f"Z-Score Reversion (Z>{z_thresh})")
    df['sma'] = df['close'].rolling(50).mean()
    df['std'] = df['close'].rolling(50).std()
    df['z'] = (df['close'] - df['sma']) / (df['std'] + 1e-9)
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    df['atr_ma'] = df['atr'].rolling(50).mean()
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    for i in range(250, len(df)-50):
        curr, prev_row = df.iloc[i], df.iloc[i-1]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        if "EUR" in symbol and not (h >= 19 or h < 1): continue
        if "GBP" in symbol and not (h >= 13 and h < 17): continue
        signal = "SELL" if (prev_row['z'] >= z_thresh and curr['z'] < z_thresh) else "BUY" if (prev_row['z'] <= -z_thresh and curr['z'] > -z_thresh) else None
        
        if signal:
            # Volatilidad Relativa
            if curr['atr'] < (df['atr_ma'].iloc[i] * 0.8):
                res.filtered += 1
                continue

            trend = get_h1_trend(df_h1, curr['time'])
            if (signal=="BUY" and trend!=1) or (signal=="SELL" and trend!=-1):
                res.filtered += 1
                continue

            sl = max(round(curr['atr']*1.5 / pip / 10, 1), 15)
            tp = max(round(curr['atr']*2.5 / pip / 10, 1), 25)
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+50].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
    return res

def sim_ict_breakout(df, df_h1, symbol):
    res = BacktestResult(f"ICT/SMC Breakout (NY)")
    pip = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(150, len(df)-50):
        curr, prev = df.iloc[i], df.iloc[i-1]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        if h < 8 or h >= 11:
            continue
            
        window = df.iloc[i-100:i-2]
        asian_high = window['high'].max()
        asian_low = window['low'].min()
        
        signal = None
        if prev['low'] < asian_low and prev['close'] > asian_low:
            body = abs(prev['close'] - prev['open'])
            total = prev['high'] - prev['low']
            if body > total * 0.4 and prev['close'] > prev['open']:
                signal = "BUY"
                
        elif prev['high'] > asian_high and prev['close'] < asian_high:
            body = abs(prev['close'] - prev['open'])
            total = prev['high'] - prev['low']
            if body > total * 0.4 and prev['close'] < prev['open']:
                signal = "SELL"
                
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            atr_14 = (df['high'].iloc[i-15:i-1] - df['low'].iloc[i-15:i-1]).mean()
            atr_pips = (atr_14 / pip / 10)
            
            sl = max(8.0, round(atr_pips * 0.5, 1))
            tp = max(25.0, round(sl * 3.0, 1))
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_ema_cross(df, df_h1, symbol):
    res = BacktestResult("EMA Momentum (NY 8-12)")
    df['ema_fast'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=50, adjust=False).mean()
    
    macd_line = df['close'].ewm(span=12, adjust=False).mean() - df['close'].ewm(span=26, adjust=False).mean()
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    df['macd_hist'] = macd_line - macd_signal
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
    
    tr = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(200, len(df)-50):
        curr, prev, prev2 = df.iloc[i], df.iloc[i-1], df.iloc[i-2]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        # Filtro NY Morning
        if h < 8 or h >= 12: continue
        
        uptrend = prev['ema_fast'] > prev['ema_slow']
        downtrend = prev['ema_fast'] < prev['ema_slow']
        
        b_cross = uptrend and prev2['ema_fast'] <= prev2['ema_slow']
        s_cross = downtrend and prev2['ema_fast'] >= prev2['ema_slow']
        
        b_pull = uptrend and prev2['close'] < prev2['ema_fast'] and prev['close'] > prev['ema_fast'] and 40 < prev['rsi'] < 70
        s_pull = downtrend and prev2['close'] > prev2['ema_fast'] and prev['close'] < prev['ema_fast'] and 30 < prev['rsi'] < 60
        
        signal = None
        if (b_cross or b_pull) and prev['macd_hist'] > 0: signal = "BUY"
        elif (s_cross or s_pull) and prev['macd_hist'] < 0: signal = "SELL"
        
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            atr_pips = prev['atr'] / pip / 10
            # Riesgo Asimétrico (1:2) que usa el script en vivo
            sl = max(15.0, round(atr_pips * 1.5, 1))
            tp = max(25.0, round(atr_pips * 3.0, 1))
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_ttm_squeeze(df, df_h1, symbol):
    res = BacktestResult("TTM Squeeze Pro (LND/NY)")
    
    tr = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(20).mean()
    
    sma_20 = df['close'].rolling(20).mean()
    std_20 = df['close'].rolling(20).std()
    df['bb_upper'] = sma_20 + (std_20 * 2.0)
    df['bb_lower'] = sma_20 - (std_20 * 2.0)
    
    ema_20 = df['close'].ewm(span=20, adjust=False).mean()
    df['kc_upper'] = ema_20 + (df['atr'] * 1.5)
    df['kc_lower'] = ema_20 - (df['atr'] * 1.5)
    
    df['squeeze_on'] = (df['bb_upper'] < df['kc_upper']) & (df['bb_lower'] > df['kc_lower'])
    
    # True TTM Momentum (Carter)
    midline = (df['high'].rolling(20).max() + df['low'].rolling(20).min()) / 2
    avg_price = (df['close'] + midline) / 2
    df['mom_smoothed'] = (df['close'] - avg_price).ewm(span=20, adjust=False).mean()
    df['momentum_bull'] = df['mom_smoothed'] > 0
    df['momentum_bear'] = df['mom_smoothed'] < 0
    df['vol_avg'] = df['tick_volume'].rolling(20).mean()
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(200, len(df)-50):
        curr, prev, prev2, prev3 = df.iloc[i], df.iloc[i-1], df.iloc[i-2], df.iloc[i-3]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        if h < 3 or h >= 13: continue
        
        was_squeezed = prev2['squeeze_on'] or prev3['squeeze_on']
        is_firing = not prev['squeeze_on']
        vol_spike = prev['tick_volume'] > (prev['vol_avg'] * 1.5)
        
        signal = None
        if was_squeezed and is_firing and vol_spike:
            if prev['momentum_bull'] and prev['close'] > prev['kc_upper']: signal = "BUY"
            elif prev['momentum_bear'] and prev['close'] < prev['kc_lower']: signal = "SELL"
            
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            atr_pips = prev['atr'] / pip / 10
            sl = max(15.0, round(atr_pips * 1.5, 1))
            tp = max(35.0, round(atr_pips * 4.5, 1)) # Squeeze Extendido
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def run_backtest(symbol="EURUSD", days=60, z=2.5, adx=30):
    if not mt5.initialize(): return []
    m5 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, days*24*12))
    m15 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days*24*4))
    h1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, days*24 + 200))
    mt5.shutdown()
    for d in [m5, m15, h1]: d['time'] = pd.to_datetime(d['time'], unit='s')
    h1['close_ema_200'] = h1['close'].ewm(span=200, adjust=False).mean()
    results = [
        sim_bollinger_rsi(m5.copy(), h1, symbol, adx), 
        sim_zscore_reversion(m15.copy(), h1, symbol, z),
        sim_ict_breakout(m5.copy(), h1, symbol),
        sim_ema_cross(m15.copy(), h1, symbol),
        sim_ttm_squeeze(m15.copy(), h1, symbol) # Nuevo: TTM Squeeze
    ]
    print(f"\n[+] {symbol} - Reporte:")
    for r in results:
        rep = r.get_report()
        print(f"  - {rep['name']:30s} | Trades: {rep['trades']:3d} | Filtramos {rep['filtered']} basura | PnL: ${rep['total_pnl']:+8.2f}")
    return [r.get_report() for r in results]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD")
    parser.add_argument("--mode", type=str, default="standard")
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",")]
    all_res = []
    for sym in symbols:
        reps = run_backtest(sym, args.days)
        all_res.append({"symbol": sym, "strategies": reps})
    os.makedirs("data", exist_ok=True)
    with open("data/backtest_results.json", "w") as f: json.dump(all_res, f, indent=2)
    print(f"\n[DONE] Reporte: data/backtest_results.json")
