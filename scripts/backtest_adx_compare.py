"""
📊 COMPARATIVA ADX THRESHOLD: 35 vs 40 vs 45
=============================================
Simula Bollinger+RSI con diferentes umbrales de ADX
para ver el impacto en PnL, Win Rate y Drawdown.

Ejecutar desde el VPS (requiere MT5):
  python scripts/backtest_adx_compare.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════
COMMISSION_PER_LOT = 9.0
SPREAD_PIPS_SIM    = 1.5
INITIAL_BALANCE    = 50000.0
RISK_PER_TRADE_PCT = 0.4
DAYS = 90  # 3 meses de datos

def calculate_adx(df, period=14):
    """Calcula ADX real (igual que el bot)"""
    high = df['high']
    low = df['low']
    close = df['close']
    
    plus_dm = high.diff()
    minus_dm = low.diff().abs() * -1  # negativo
    minus_dm = low.shift(1) - low  # Corrección
    
    plus_dm = high - high.shift(1)
    minus_dm_raw = low.shift(1) - low
    
    plus_dm = plus_dm.where((plus_dm > minus_dm_raw) & (plus_dm > 0), 0)
    minus_dm = minus_dm_raw.where((minus_dm_raw > plus_dm) & (minus_dm_raw > 0), 0)
    
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
    
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx

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

def sim_bollinger_rsi_with_adx(df, df_h1, symbol, adx_threshold):
    """Simulador FIEL al bot real con filtro ADX"""
    
    # Indicadores
    df['sma20'] = df['close'].rolling(20).mean()
    df['std20'] = df['close'].rolling(20).std()
    mult = 2.3 if "EUR" in symbol else 1.9
    df['bb_upper'] = df['sma20'] + df['std20'] * mult
    df['bb_lower'] = df['sma20'] - df['std20'] * mult
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss))
    
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    df['adx'] = calculate_adx(df, 14)
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    
    trades = []
    wins = 0
    losses = 0
    filtered_adx = 0
    filtered_other = 0
    total_pnl = 0.0
    balance = INITIAL_BALANCE
    peak = INITIAL_BALANCE
    max_dd = 0.0
    consecutive_losses = 0
    max_consecutive_losses = 0
    
    for i in range(50, len(df) - 50):
        row = df.iloc[i]
        h = (pd.Timestamp(row['time']).hour - 5) % 24
        
        # Filtro horario (idéntico al bot)
        if "EUR" in symbol and not (h >= 19 or h < 1): continue
        if "GBP" in symbol and not (h >= 13 and h < 17): continue
        
        # ─── FILTRO ADX ───
        if pd.notna(row['adx']) and row['adx'] > adx_threshold:
            # Contar cuántas señales potenciales se pierden
            signal_check = ("BUY" if (row['close'] <= row['bb_lower'] and row['rsi'] <= 32) 
                           else "SELL" if (row['close'] >= row['bb_upper'] and row['rsi'] >= 68)
                           else None)
            if signal_check:
                filtered_adx += 1
            continue
        
        # Señal
        signal = None
        if row['close'] <= row['bb_lower'] and row['rsi'] <= 32:
            signal = "BUY"
        elif row['close'] >= row['bb_upper'] and row['rsi'] >= 68:
            signal = "SELL"
        
        if not signal:
            continue
        
        # Wick rejection (fiel al bot)
        if row['open'] < row['close']:
            lower_wick = row['open'] - row['low']
            upper_wick = row['high'] - row['close']
        else:
            lower_wick = row['close'] - row['low']
            upper_wick = row['high'] - row['open']
        cuerpo = abs(row['close'] - row['open'])
        
        if signal == "BUY" and not (lower_wick > cuerpo * 0.8):
            filtered_other += 1
            continue
        if signal == "SELL" and not (upper_wick > cuerpo * 0.8):
            filtered_other += 1
            continue
        
        # H1 Trend Filter
        trend = get_h1_trend(df_h1, row['time'])
        if signal == "BUY" and trend == -1:
            filtered_other += 1
            continue
        if signal == "SELL" and trend == 1:
            filtered_other += 1
            continue
        
        # Calcular SL/TP
        sl = max(round(row['atr'] * 1.5 / pip / 10, 1), 8.0)
        tp = max(round(row['atr'] * 2.0 / pip / 10, 1), 15.0)
        
        pnl = calculate_pnl(signal, row['close'], sl, tp, df.iloc[i+1:i+50].to_dict('records'), symbol)
        
        total_pnl += pnl
        balance += pnl
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
        
        if pnl > 0:
            wins += 1
            consecutive_losses = 0
        elif pnl < 0:
            losses += 1
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        trades.append({"pnl": pnl, "hour": h, "signal": signal, "adx": row['adx']})
    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    
    gross_wins = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    pf = (gross_wins / gross_losses) if gross_losses > 0 else 999
    
    return {
        "adx_threshold": adx_threshold,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(pf, 2),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_dd, 2),
        "max_consecutive_losses": max_consecutive_losses,
        "filtered_by_adx": filtered_adx,
        "filtered_by_other": filtered_other,
        "avg_adx_on_trade": round(np.mean([t["adx"] for t in trades]) if trades else 0, 1),
    }

def main():
    if not mt5.initialize():
        print("❌ Error: No se pudo conectar a MetaTrader 5")
        return
    
    print("=" * 70)
    print("  📊 COMPARATIVA ADX THRESHOLD - BOLLINGER+RSI")
    print("  📅 Datos: Últimos 90 días | Riesgo: 0.4% por trade")
    print("=" * 70)
    
    for symbol in ["GBPUSD", "EURUSD"]:
        print(f"\n{'─' * 70}")
        print(f"  🔍 {symbol}")
        print(f"{'─' * 70}")
        
        # Cargar datos
        m5 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, DAYS * 24 * 12))
        h1 = pd.DataFrame(mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, DAYS * 24 + 200))
        
        if m5.empty or h1.empty:
            print(f"  ⚠️ Sin datos para {symbol}")
            continue
        
        for d in [m5, h1]:
            d['time'] = pd.to_datetime(d['time'], unit='s')
        h1['close_ema_200'] = h1['close'].ewm(span=200, adjust=False).mean()
        
        # Correr con diferentes thresholds
        thresholds = [30, 35, 40, 45, 50, 999]  # 999 = sin filtro ADX
        results = []
        
        for adx_t in thresholds:
            res = sim_bollinger_rsi_with_adx(m5.copy(), h1, symbol, adx_t)
            results.append(res)
        
        # Tabla de resultados
        print(f"\n  {'ADX':<8} {'Trades':<8} {'Wins':<6} {'Loss':<6} {'WR%':<7} {'PF':<6} {'PnL':<12} {'MaxDD':<10} {'MaxLoss':<9} {'Filtrado ADX':<13}")
        print(f"  {'─'*8} {'─'*8} {'─'*6} {'─'*6} {'─'*7} {'─'*6} {'─'*12} {'─'*10} {'─'*9} {'─'*13}")
        
        for r in results:
            label = f"< {r['adx_threshold']}" if r['adx_threshold'] < 999 else "SIN FLT"
            
            # Colorear veredicto
            if r['profit_factor'] >= 1.5 and r['win_rate'] >= 45:
                verdict = "🟢"
            elif r['profit_factor'] >= 1.05:
                verdict = "🟡"
            elif r['total_trades'] == 0:
                verdict = "⚪"
            else:
                verdict = "🔴"
            
            print(f"  {label:<8} {r['total_trades']:<8} {r['wins']:<6} {r['losses']:<6} "
                  f"{r['win_rate']:<7} {r['profit_factor']:<6} ${r['total_pnl']:>+9.2f}  "
                  f"${r['max_drawdown']:>8.2f} {r['max_consecutive_losses']:<9} "
                  f"{r['filtered_by_adx']:<13} {verdict}")
        
        # Resumen
        r35 = next(r for r in results if r['adx_threshold'] == 35)
        r45 = next(r for r in results if r['adx_threshold'] == 45)
        
        print(f"\n  📈 COMPARATIVA DIRECTA ADX 35 vs 45:")
        print(f"     Trades extra con ADX 45: +{r45['total_trades'] - r35['total_trades']}")
        print(f"     PnL diferencia:          ${r45['total_pnl'] - r35['total_pnl']:+.2f}")
        print(f"     Win Rate cambio:         {r45['win_rate'] - r35['win_rate']:+.1f}%")
        print(f"     Señales desbloqueadas:    {r35['filtered_by_adx'] - r45['filtered_by_adx']}")
    
    mt5.shutdown()
    print(f"\n{'=' * 70}")
    print("  ✅ ANÁLISIS COMPLETADO")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    main()
