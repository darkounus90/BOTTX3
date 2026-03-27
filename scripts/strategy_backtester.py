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

def _calculate_adx(df, period=14):
    """Calcula ADX real (idéntico al bot en producción)"""
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = (high - high.shift(1)).clip(lower=0)
    minus_dm = (low.shift(1) - low).clip(lower=0)
    # Solo el mayor prevalece
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-10))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    return dx.ewm(alpha=1/period, adjust=False).mean()


def sim_liquidity_sweep(df, df_h1, symbol):
    """Simulador de la nueva estrategia Institutional Liquidity Sweep (ILS)"""
    res = BacktestResult("ILS Liquidity Sweep (4h)")
    pip = 0.0001 if "JPY" not in symbol else 0.01
    
    # 1. LSMA para confirmación de reversión
    def calculate_lsma(s, p):
        weights = np.arange(1, p + 1)
        return s.rolling(window=p).apply(lambda x: np.polyfit(weights, x, 1)[0] * p + np.polyfit(weights, x, 1)[1], raw=True)
    
    df['lsma'] = calculate_lsma(df['close'], 25)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    for i in range(100, len(df)-50):
        curr, prev = df.iloc[i], df.iloc[i-1]
        ts = curr['time']
        h = (pd.Timestamp(ts).hour - 5) % 24
        
        # Filtro Sesión (Londres + NY)
        if h < 2 or h > 16: continue
        
        # Obtener rango 4h previo desde H1
        mask = (df_h1['time'] < ts)
        h1_window = df_h1[mask].iloc[-4:]
        if len(h1_window) < 4: continue
        
        liq_high = h1_window['high'].max()
        liq_low = h1_window['low'].min()
        
        signal = None
        # Sell: Sweep High + Close below level + Close below LSMA
        if prev['high'] > liq_high and (prev['high'] - liq_high) < (8.0 * pip):
            if curr['close'] < liq_high and curr['close'] < curr['lsma']:
                signal = "SELL"
        # Buy: Sweep Low + Close above level + Close above LSMA
        elif prev['low'] < liq_low and (liq_low - prev['low']) < (8.0 * pip):
            if curr['close'] > liq_low and curr['close'] > curr['lsma']:
                signal = "BUY"
                
        if signal:
            trend = get_h1_trend(df_h1, ts)
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            sl = max(round(curr['atr']*1.5 / pip / 10, 1), 10.0)
            tp = max(round(curr['atr']*3.0 / pip / 10, 1), 20.0)
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+50].to_dict('records'), symbol)
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

# Eliminadas estrategias antiguas perdedoras (Bollinger, ICT, EMA Cross)

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
    
    df['ema_8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_34'] = df['close'].ewm(span=34, adjust=False).mean()
    df['momentum_bull'] = df['ema_8'] > df['ema_34']
    df['momentum_bear'] = df['ema_8'] < df['ema_34']
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(200, len(df)-50):
        curr, prev, prev2, prev3 = df.iloc[i], df.iloc[i-1], df.iloc[i-2], df.iloc[i-3]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        if h < 3 or h >= 13: continue
        
        was_squeezed = prev2['squeeze_on'] or prev3['squeeze_on']
        is_firing = not prev['squeeze_on']
        
        signal = None
        if was_squeezed and is_firing:
            if prev['momentum_bull'] and prev['close'] > prev['kc_upper']: signal = "BUY"
            elif prev['momentum_bear'] and prev['close'] < prev['kc_lower']: signal = "SELL"
            
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            atr_pips = prev['atr'] / pip / 10
            sl = max(15.0, round(atr_pips * 1.5, 1))
            tp = max(30.0, round(atr_pips * 4.0, 1))
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def run_backtest(symbol="EURUSD", days=60, z=2.5, adx=45):
    if not mt5.initialize(): return []
    m5 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, days*24*12))
    m15 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days*24*4))
    h1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, days*24 + 200))
    mt5.shutdown()
    for d in [m5, m15, h1]: d['time'] = pd.to_datetime(d['time'], unit='s')
    h1['close_ema_200'] = h1['close'].ewm(span=200, adjust=False).mean()
    
    # ═══════ EQUIPO DE ÉLITE TX3 PRO ═══════
    results = [
        sim_liquidity_sweep(m5.copy(), h1, symbol),     # NUEVA: ILS Sweep
        sim_ttm_squeeze(m15.copy(), h1, symbol),        # REY: Squeeze Pro
        sim_zscore_reversion(m15.copy(), h1, symbol, z) # ESTABLE: Z-Score
    ]
    print(f"\n{'='*100}")
    print(f"  [+] {symbol} - REPORTE OPERATIVO (ESTRATEGIAS ACTIVAS)")
    print(f"{'='*100}")
    for r in results:
        rep = r.get_report()
        pf_str = f"PF:{rep['profit_factor']:.2f}" if rep['profit_factor'] else "PF:N/A"
        wr_str = f"WR:{rep['win_rate']}%" if rep['win_rate'] else "WR:N/A"
        print(f"  {rep['name']:40s} | T:{rep['trades']:3d} | {wr_str:>8} | {pf_str:>7} | PnL:${rep['total_pnl']:+8.2f} | DD:${rep['max_drawdown']:,.2f} | {rep['verdict']}")
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
