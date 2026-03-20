"""
📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO DE ESTRATEGIAS
=========================================================
Simula TODAS las estrategias del bot contra datos históricos reales de MT5.
Genera un veredicto frío: cuáles ganan, cuáles pierden, cuáles sobran.

Uso:
    python scripts/strategy_backtester.py
    python scripts/strategy_backtester.py --days 90 --symbol EURUSD
    python scripts/strategy_backtester.py --mode sensitivity
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
import argparse
import json

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DEL BACKTEST
# ═══════════════════════════════════════════════════════════════

COMMISSION_PER_LOT = 9.0      # USD por lote (ida y vuelta FTMO)
SPREAD_PIPS_SIM    = 1.5      # Spread promedio simulado
SLIPPAGE_PIPS      = 0.3      # Slippage realista
INITIAL_BALANCE    = 50000.0
RISK_PER_TRADE_PCT = 0.4      # Igual que tu config real


class BacktestResult:
    """Almacena resultados de una estrategia individual"""
    def __init__(self, name):
        self.name = name
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_balance = INITIAL_BALANCE
        self.balance = INITIAL_BALANCE
        self.best_trade = 0.0
        self.worst_trade = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.consecutive_losses_max = 0
        self._current_consecutive_losses = 0
        self.win_by_hour = defaultdict(lambda: {"wins": 0, "losses": 0})
    
    def add_trade(self, pnl, hour, direction, sl_pips, tp_pips):
        self.trades.append({"pnl": pnl, "hour": hour, "dir": direction, "sl": sl_pips, "tp": tp_pips})
        self.total_pnl += pnl
        self.balance += pnl
        
        if pnl > 0:
            self.wins += 1
            self._current_consecutive_losses = 0
            self.win_by_hour[hour]["wins"] += 1
        else:
            self.losses += 1
            self._current_consecutive_losses += 1
            self.consecutive_losses_max = max(self.consecutive_losses_max, self._current_consecutive_losses)
            self.win_by_hour[hour]["losses"] += 1
        
        self.best_trade = max(self.best_trade, pnl)
        self.worst_trade = min(self.worst_trade, pnl)
        
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        dd = self.peak_balance - self.balance
        self.max_drawdown = max(self.max_drawdown, dd)
    
    def get_report(self):
        total = self.wins + self.losses
        if total == 0:
            return {"name": self.name, "trades": 0, "verdict": "SIN DATOS"}
        
        win_rate = (self.wins / total) * 100
        avg_w = sum(t["pnl"] for t in self.trades if t["pnl"] > 0) / max(self.wins, 1)
        avg_l = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0) / max(self.losses, 1))
        profit_factor = (avg_w * self.wins) / max(avg_l * self.losses, 1)
        expectancy = (win_rate/100 * avg_w) - ((1 - win_rate/100) * avg_l)
        
        # Mejor hora para operar
        best_hour = None
        best_hour_wr = 0
        for h, data in self.win_by_hour.items():
            t = data["wins"] + data["losses"]
            if t >= 3:  # Mínimo 3 trades para que sea estadísticamente relevante
                wr = data["wins"] / t * 100
                if wr > best_hour_wr:
                    best_hour_wr = wr
                    best_hour = h
        
        # VEREDICTO ALGORÍTMICO
        if total < 5:
            verdict = "⚠️ DATOS INSUFICIENTES"
            verdict_code = "INSUF"
        elif profit_factor >= 1.5 and win_rate >= 50 and expectancy > 0:
            verdict = "🟢 MANTENER (Rentable)"
            verdict_code = "KEEP"
        elif profit_factor >= 1.0 and expectancy > 0:
            verdict = "🟡 OPTIMIZAR (Potencial)"
            verdict_code = "OPTIMIZE"
        else:
            verdict = "🔴 DESACTIVAR (Destruye Capital)"
            verdict_code = "DISABLE"
        
        return {
            "name": self.name,
            "trades": total,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 1),
            "profit_factor": round(profit_factor, 2),
            "expectancy_usd": round(expectancy, 2),
            "total_pnl": round(self.total_pnl, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2),
            "avg_win": round(avg_w, 2),
            "avg_loss": round(avg_l, 2),
            "max_consecutive_losses": self.consecutive_losses_max,
            "best_hour_est": best_hour,
            "best_hour_winrate": round(best_hour_wr, 1),
            "verdict": verdict,
            "verdict_code": verdict_code
        }


# ═══════════════════════════════════════════════════════════════
#  SIMULADORES DE ESTRATEGIAS (Réplicas exactas de tu código)
# ═══════════════════════════════════════════════════════════════

def calculate_pnl(direction, entry_price, sl_pips, tp_pips, future_candles, symbol):
    """
    Simula la evolución del trade mirando velas futuras.
    Retorna el PnL real en USD (con comisión y slippage).
    """
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    
    sl_price_dist = sl_pips * pip_size
    tp_price_dist = tp_pips * pip_size
    spread_dist   = SPREAD_PIPS_SIM * pip_size
    
    if direction == "BUY":
        effective_entry = entry_price + spread_dist
        sl_price = effective_entry - sl_price_dist
        tp_price = effective_entry + tp_price_dist
    else:
        effective_entry = entry_price - spread_dist
        sl_price = effective_entry + sl_price_dist
        tp_price = effective_entry - tp_price_dist
    
    for candle in future_candles:
        if direction == "BUY":
            if candle["low"] <= sl_price:
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return -risk_usd
            if candle["high"] >= tp_price:
                reward_ratio = tp_pips / sl_pips
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return risk_usd * reward_ratio - COMMISSION_PER_LOT * 0.1
        else:
            if candle["high"] >= sl_price:
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return -risk_usd
            if candle["low"] <= tp_price:
                reward_ratio = tp_pips / sl_pips
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return risk_usd * reward_ratio - COMMISSION_PER_LOT * 0.1
    
    # Cierre por tiempo (velas agotadas)
    last_close = future_candles[-1]["close"] if len(future_candles) > 0 else entry_price
    pips_result = (last_close - effective_entry) / pip_size if direction == "BUY" else (effective_entry - last_close) / pip_size
    risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
    return (pips_result / sl_pips) * risk_usd - COMMISSION_PER_LOT * 0.05


def sim_bollinger_rsi(df, symbol, adx_threshold=35.0):
    result = BacktestResult(f"Bollinger+RSI (ADX < {adx_threshold})")
    
    bb_period, bb_dev = 20, 1.9
    rsi_period, rsi_ob, rsi_os = 14, 68.0, 32.0
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss_s = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/rsi_period, adjust=False).mean()
    avg_loss = loss_s.ewm(alpha=1/rsi_period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['sma_20'] = df['close'].rolling(window=bb_period).mean()
    df['std_20'] = df['close'].rolling(window=bb_period).std()
    df['bb_upper'] = df['sma_20'] + (df['std_20'] * bb_dev)
    df['bb_lower'] = df['sma_20'] - (df['std_20'] * bb_dev)
    
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX
    plus_dm = np.where((df['high'].diff() > df['low'].shift() - df['low']) & (df['high'].diff() > 0), df['high'].diff(), 0.0)
    minus_dm = np.where((df['low'].shift() - df['low'] > df['high'].diff()) & (df['low'].shift() - df['low'] > 0), df['low'].shift() - df['low'], 0.0)
    tr_smooth = tr.rolling(window=14).sum()
    plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / (tr_smooth + 1e-9))
    dx = (abs(plus_di - minus_di) / (abs(plus_di + minus_di) + 1e-9)) * 100
    df['adx'] = dx.rolling(14).mean()
    
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(50, len(df) - 50):
        row = df.iloc[i]
        if row['adx'] > adx_threshold: continue
        
        candle_hour_est = (pd.Timestamp(row['time']).hour - 5) % 24
        if "EUR" in symbol and (candle_hour_est < 3 or candle_hour_est >= 7): continue
        if "GBP" in symbol and not (candle_hour_est >= 17 or candle_hour_est < 1): continue
        
        lower_wick = min(row['open'], row['close']) - row['low']
        upper_wick = row['high'] - max(row['open'], row['close'])
        cuerpo = abs(row['close'] - row['open'])

        signal = None
        if row['close'] < row['bb_lower'] and row['rsi'] < rsi_os and lower_wick > cuerpo:
            signal = "BUY"
        elif row['close'] > row['bb_upper'] and row['rsi'] > rsi_ob and upper_wick > cuerpo:
            signal = "SELL"
        
        if signal:
            sl_pips = max(round((row['atr'] * 1.5) / pip_size / 10, 1), 20)
            tp_pips = max(round((row['atr'] * 2.5) / pip_size / 10, 1), 40)
            future = df.iloc[i+1:i+50].to_dict('records')
            pnl = calculate_pnl(signal, row['close'], sl_pips, tp_pips, future, symbol)
            result.add_trade(pnl, candle_hour_est, signal, sl_pips, tp_pips)
    
    return result


def sim_ema_cross(df, symbol):
    result = BacktestResult("Dynamic Momentum Pro (EMA Cross)")
    ema_fast, ema_slow = 20, 50
    df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()
    
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift(1))
    low_close = abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    for i in range(55, len(df) - 50):
        prev, curr = df.iloc[i-1], df.iloc[i]
        signal = None
        if prev['ema_fast'] <= prev['ema_slow'] and curr['ema_fast'] > curr['ema_slow']:
            signal = "BUY"
        elif prev['ema_fast'] >= prev['ema_slow'] and curr['ema_fast'] < curr['ema_slow']:
            signal = "SELL"
            
        if signal:
            sl_pips = max(round((curr['atr'] * 1.5) / pip_size / 10, 1), 20)
            tp_pips = max(round((curr['atr'] * 3.0) / pip_size / 10, 1), 40)
            future = df.iloc[i+1:i+50].to_dict('records')
            pnl = calculate_pnl(signal, curr['close'], sl_pips, tp_pips, future, symbol)
            hour_est = (pd.Timestamp(curr['time']).hour - 5) % 24
            result.add_trade(pnl, hour_est, signal, sl_pips, tp_pips)
    return result

def sim_zscore_reversion(df, symbol, z_threshold=2.5):
    result = BacktestResult(f"Z-Score Reversion (Z > {z_threshold})")
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['std_50'] = df['close'].rolling(window=50).std()
    df['z_score'] = (df['close'] - df['sma_50']) / (df['std_50'] + 1e-9)
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    for i in range(250, len(df) - 50):
        prev, curr = df.iloc[i-1], df.iloc[i]
        signal = None
        if prev['z_score'] >= z_threshold and curr['z_score'] < z_threshold and curr['close'] < curr['ema_200']:
            signal = "SELL"
        elif prev['z_score'] <= -z_threshold and curr['z_score'] > -z_threshold and curr['close'] > curr['ema_200']:
            signal = "BUY"
            
        if signal:
            sl_pips = max(round((curr['atr'] * 1.5) / pip_size / 10, 1), 15)
            tp_pips = max(round((curr['atr'] * 2.5) / pip_size / 10, 1), 25)
            future = df.iloc[i+1:i+50].to_dict('records')
            pnl = calculate_pnl(signal, curr['close'], sl_pips, tp_pips, future, symbol)
            result.add_trade(pnl, (pd.Timestamp(curr['time']).hour - 5) % 24, signal, sl_pips, tp_pips)
    return result

def run_backtest(symbol="EURUSD", days=60, z_thresh=2.5, adx_thresh=35.0):
    if not mt5.initialize(): return []
    m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, days * 24 * 12)
    m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days * 24 * 4)
    mt5.shutdown()
    
    if m5_rates is None or m15_rates is None: return []
    df5, df15 = pd.DataFrame(m5_rates), pd.DataFrame(m15_rates)
    df5['time'] = pd.to_datetime(df5['time'], unit='s')
    df15['time'] = pd.to_datetime(df15['time'], unit='s')
    
    results = [
        sim_bollinger_rsi(df5.copy(), symbol, adx_threshold=adx_thresh),
        sim_ema_cross(df5.copy(), symbol),
        sim_zscore_reversion(df15.copy(), symbol, z_threshold=z_thresh)
    ]
    
    print(f"\n[+] BACKTEST {symbol} | Z={z_thresh} | ADX={adx_thresh}")
    for r in results:
        rep = r.get_report()
        if rep['trades'] > 0:
            print(f"  - {rep['name']:30s} | Trades: {rep['trades']:3d} | P&L: ${rep['total_pnl']:+8.2f}")
            
    return [r.get_report() for r in results]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--symbols", type=str, default="EURUSD,GBPUSD")
    parser.add_argument("--mode", type=str, default="standard")
    args = parser.parse_args()
    
    symbols = [s.strip() for s in args.symbols.split(",")]
    all_runs = []
    
    if args.mode == "sensitivity":
        configs = [("RIGIDO", 2.5, 35.0), ("EQUILIBRADO", 2.2, 30.0), ("AGRESIVO", 2.0, 25.0)]
        for sym in symbols:
            sym_results = {"symbol": sym, "runs": []}
            for name, z, adx in configs:
                reps = run_backtest(sym, args.days, z, adx)
                sym_results["runs"].append({"config": name, "z": z, "adx": adx, "strategies": reps})
            all_runs.append(sym_results)
    else:
        for sym in symbols:
            reps = run_backtest(sym, args.days)
            all_runs.append({"symbol": sym, "strategies": reps})
            
    output_path = os.path.join("data", "backtest_results.json")
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_runs, f, indent=2)
    print(f"\n[🚀] REPORTE FINAL EN: {output_path}")
