"""
📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO DE ALTA FIDELIDAD (V2 - OPTIMIZADO)
========================================================================
Simula las estrategias del bot con los mismos filtros institucionales 
que el sistema real: Tendencia H1, MACD, Wick Rejection, Volatilidad y Slope.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix for windows console emoji print crash
sys.stdout.reconfigure(encoding='utf-8')

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
import argparse
import json
import joblib

# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN DEL BACKTEST
# ═══════════════════════════════════════════════════════════════

COMMISSION_PER_LOT = 9.0      
SPREAD_PIPS_SIM    = 1.5      
INITIAL_BALANCE    = 50000.0
RISK_PER_TRADE_PCT = 1.0      

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
    pip = 1.0 if "US100" in symbol or "NAS" in symbol else (0.01 if "JPY" in symbol else 0.0001)
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
    """Simulador mejorado de ILS Sweep (detecta 1-candle sweeps)"""
    res = BacktestResult("ILS Liquidity Sweep (4h)")
    pip = 0.0001 if "JPY" not in symbol else 0.01
    
    def calculate_lsma(s, p):
        weights = np.arange(1, p + 1)
        return s.rolling(window=p).apply(lambda x: np.polyfit(weights, x, 1)[0] * p + np.polyfit(weights, x, 1)[1], raw=True)
    
    df['lsma'] = calculate_lsma(df['close'], 25)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()

    potential_signals = 0

    for i in range(100, len(df)-50):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        ts = curr['time']
        h = (pd.Timestamp(ts).hour - 5) % 24
        
        if h < 2 or h >= 13: continue
        
        mask = (df_h1['time'] < ts)
        h1_window = df_h1[mask].iloc[-4:]
        if len(h1_window) < 4: continue
        
        liq_high = h1_window['high'].max()
        liq_low = h1_window['low'].min()
        
        signal = None
        
        # --- NUEVA LÓGICA: SENSIVILIDAD AUMENTADA ---
        # Caso A: Barrido y rechazo en UNA sola vela (mecha larga)
        if curr['high'] > liq_high and curr['close'] < liq_high:
            if (curr['high'] - liq_high) < (15.0 * pip): # Barrido < 15 pips
                signal = "SELL"
        
        # Caso B: Barrido en vela previa, cierre en la actual
        elif prev['high'] > liq_high and curr['close'] < liq_high:
            if (prev['high'] - liq_high) < (15.0 * pip):
                signal = "SELL"

        # Simétrico para BUY
        if curr['low'] < liq_low and curr['close'] > liq_low:
            if (liq_low - curr['low']) < (15.0 * pip):
                signal = "BUY"
        elif prev['low'] < liq_low and curr['close'] > liq_low:
            if (liq_low - prev['low']) < (15.0 * pip):
                signal = "BUY"
                
        if signal:
            potential_signals += 1
            trend_h1 = get_h1_trend(df_h1, ts)
            if (signal == "BUY" and trend_h1 == -1) or (signal == "SELL" and trend_h1 == 1):
                res.filtered += 1
                signal = None
                
        if signal:
            # Mantener filtro de tendencia pero menos agresivo (usando LSMA M5)
            if signal == "SELL" and curr['close'] > curr['lsma']: continue
            if signal == "BUY" and curr['close'] < curr['lsma']: continue
                
            sl = max(round(curr['atr']*1.5 / pip / 10, 1), 12.0)
            tp = max(round(curr['atr']*3.0 / pip / 10, 1), 24.0)
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+50].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    if res.trades:
        print(f"  [DEBUG] {symbol} ILS: {potential_signals} barridos detectados -> {len(res.trades)} trades ejecutados.")
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
        if "GBP" in symbol and not (h >= 3 and h < 13): continue
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

def sim_silver_bullet(df, df_h1, symbol):
    """Simulador ICT Silver Bullet NY ELITE (10:00 - 11:00 AM EST)"""
    res = BacktestResult("ICT Silver Bullet (NY Elite)")
    pip = 0.0001 if "JPY" not in symbol else 0.01
    last_trade_day = None
    
    def find_fvgs(df_window):
        fvgs = []
        for j in range(len(df_window)-1, 1, -1):
            if j < 2: continue
            if df_window.iloc[j]['low'] > df_window.iloc[j-2]['high']:
                fvgs.append({'type': 'BULLISH', 'top': df_window.iloc[j]['low'], 'bottom': df_window.iloc[j-2]['high'], 'mid': (df_window.iloc[j]['low'] + df_window.iloc[j-2]['high']) / 2})
            elif df_window.iloc[j]['high'] < df_window.iloc[j-2]['low']:
                fvgs.append({'type': 'BEARISH', 'top': df_window.iloc[j-2]['low'], 'bottom': df_window.iloc[j]['high'], 'mid': (df_window.iloc[j-2]['low'] + df_window.iloc[j]['high']) / 2})
        return fvgs

    for i in range(100, len(df)-50):
        curr = df.iloc[i]
        ts = curr['time']
        day = ts.date()
        h = (pd.Timestamp(ts).hour - 5) % 24
        
        if h != 10 or day == last_trade_day: continue
        
        # 1. Obtener Sweep H1 (desde hace 8 horas: cubre Londres y NY)
        mask = df_h1['time'] < ts
        h1_recent = df_h1[mask].iloc[-8:] 
        liq_high = h1_recent['high'].max()
        liq_low = h1_recent['low'].min()
        
        has_swept_high = df['high'].iloc[i-100:i+1].max() > liq_high
        has_swept_low = df['low'].iloc[i-100:i+1].min() < liq_low

        # 2. Detectar FVG
        window = df.iloc[i-15:i+1]
        fvgs = find_fvgs(window)
        if not fvgs: continue
        
        last_fvg = fvgs[0]
        signal = None
        
        if has_swept_low and last_fvg['type'] == 'BULLISH':
            if curr['low'] <= last_fvg['top'] and curr['close'] > last_fvg['mid']:
                signal = "BUY"
        elif has_swept_high and last_fvg['type'] == 'BEARISH':
            if curr['high'] >= last_fvg['bottom'] and curr['close'] < last_fvg['mid']:
                signal = "SELL"
                
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                signal = None
                
        if signal:
            disp_pips = abs(curr['close'] - df.iloc[i-5]['open']) / (10 * pip)
            if disp_pips < 4.5: continue # Filtro suave: el escudo principal ahora es HTF Trend
            
            last_trade_day = day
            sl = max(12.0, round(disp_pips * 0.7, 1))
            tp = max(24.0, sl * 2.5) 
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+60].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_london_purge(df, df_h1, symbol):
    """Simulador SMC 2.1: London Open Purge con Filtro de Tendencia (HTF)"""
    res = BacktestResult("London Open Purge (SMC 2.1)")
    pip = 0.0001 if "JPY" not in symbol else 0.01
    last_trade_day = None
    
    def get_asia_range(full_df, current_ts):
        """Busca el rango de Asia (7 PM - 2 AM EST)"""
        mask = (full_df['time'] < current_ts)
        # Últimas 100 velas M5 aprox cubren Asia
        window = full_df[mask].iloc[-120:] 
        
        asia_high = -1e9
        asia_low = 1e9
        found = False
        
        for _, row in window.iterrows():
            h = (pd.Timestamp(row['time']).hour - 5) % 24
            if h >= 19 or h < 2:
                asia_high = max(asia_high, row['high'])
                asia_low = min(asia_low, row['low'])
                found = True
        return (asia_high, asia_low) if found else (None, None)

    for i in range(120, len(df)-50):
        curr = df.iloc[i]
        ts = curr['time']
        day = ts.date()
        h = (pd.Timestamp(ts).hour - 5) % 24
        
        # Ventana de Apertura de Londres (3-5 AM EST)
        if h < 3 or h > 5 or day == last_trade_day: continue
        
        # 1. Obtener Asia Range
        asia_high, asia_low = get_asia_range(df, ts)
        if not asia_high: continue
        
        # 2. Verificar Barrido (Liquidity Sweep)
        # ¿La vela actual o las anteriores barreron el rango?
        has_swept_high = df['high'].iloc[i-12:i+1].max() > asia_high
        has_swept_low = df['low'].iloc[i-12:i+1].min() < asia_low
        
        # 3. Gatillo: Retorno al Rango + FVG
        # Buscar FVG en los últimos 20 mins
        fvgs = []
        for j in range(i, i-20, -1):
            if j < 2: break
            if df.iloc[j]['low'] > df.iloc[j-2]['high']:
                fvgs.append({'type': 'BULLISH', 'top': df.iloc[j]['low'], 'bottom': df.iloc[j-2]['high']})
            elif df.iloc[j]['high'] < df.iloc[j-2]['low']:
                fvgs.append({'type': 'BEARISH', 'top': df.iloc[j-2]['low'], 'bottom': df.iloc[j]['high']})
                
        if not fvgs: continue
        last_fvg = fvgs[0]
        signal = None
        
        # BULLISH (Se barrió el bajo de Asia y ahora recupera)
        if has_swept_low and last_fvg['type'] == 'BULLISH' and curr['close'] > asia_low:
             signal = "BUY"
        # BEARISH (Se barrió el alto de Asia y ahora recupera)
        elif has_swept_high and last_fvg['type'] == 'BEARISH' and curr['close'] < asia_high:
             signal = "SELL"
                 
        if signal:
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                signal = None

        if signal:
            disp_pips = abs(curr['close'] - df.iloc[i-5]['open']) / (10 * pip)
            if disp_pips < 5.0: continue # Filtro suave: el escudo real es HTF EMA200
            
            last_trade_day = day
            sl = max(12.0, round(disp_pips * 0.8, 1))
            tp = max(36.0, sl * 3.0) 
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+60].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

# Eliminadas estrategias antiguas perdedoras (Bollinger, ICT, EMA Cross)

def sim_institutional_flow(df_m5, df_m15, df_h1, symbol):
    """Simulador de la nueva estrategia IFS SMC 2.0 (Inbalance + Mitigation)"""
    res = BacktestResult("IFS SMC 2.0 (M15 FVG)")
    pip = 0.0001 if "JPY" not in symbol else 0.01
    
    def find_fvgs(df):
        fvgs = []
        for i in range(1, len(df)-2):
            if df.iloc[i+2]['low'] > df.iloc[i]['high']:
                fvgs.append({'type': 'BULLISH', 'top': df.iloc[i+2]['low'], 'bottom': df.iloc[i]['high'], 'mid': (df.iloc[i+2]['low'] + df.iloc[i]['high']) / 2})
            elif df.iloc[i+2]['high'] < df.iloc[i]['low']:
                fvgs.append({'type': 'BEARISH', 'top': df.iloc[i]['low'], 'bottom': df.iloc[i+2]['high'], 'mid': (df.iloc[i]['low'] + df.iloc[i+2]['high']) / 2})
        return fvgs

    # ATR para SL/TP
    tr = pd.concat([df_m5['high'] - df_m5['low'], (df_m5['high'] - df_m5['close'].shift()).abs(), (df_m5['low'] - df_m5['close'].shift()).abs()], axis=1).max(axis=1)
    df_m5['atr'] = tr.rolling(14).mean()
    df_m5['ma10'] = df_m5['close'].rolling(10).mean()

    for i in range(100, len(df_m5)-50):
        curr = df_m5.iloc[i]
        prev = df_m5.iloc[i-1]
        ts = curr['time']
        h = (pd.Timestamp(ts).hour - 5) % 24
        
        # Filtro Sesión (Institucional)
        if h < 2 or h >= 13: continue
        
        # Buscar contexto en M15
        mask = (df_m15['time'] < ts)
        m15_window = df_m15[mask].iloc[-50:]
        if len(m15_window) < 5: continue
        
        fvgs = find_fvgs(m15_window)
        if not fvgs: continue
        
        last_fvg = fvgs[-1]
        signal = None
        
        trend_h1 = get_h1_trend(df_h1, ts)
        
        # Caso Bullish FVG
        if last_fvg['type'] == 'BULLISH' and trend_h1 == 1:
            # El precio toca la zona de mitigación
            if curr['close'] < last_fvg['top'] and curr['close'] > last_fvg['bottom']:
                recent_high = df_m5.iloc[i-3:i]['high'].max()
                if curr['close'] > recent_high and curr['close'] > curr['ma10']:
                    signal = "BUY"
                    
        # Caso Bearish FVG
        elif last_fvg['type'] == 'BEARISH' and trend_h1 == -1:
            if curr['close'] > last_fvg['bottom'] and curr['close'] < last_fvg['top']:
                recent_low = df_m5.iloc[i-3:i]['low'].min()
                if curr['close'] < recent_low and curr['close'] < curr['ma10']:
                    signal = "SELL"
                    
        if signal:
            sl = max(round(curr['atr']*1.2 / pip / 10, 1), 10.0)
            tp = max(round(curr['atr']*3.5 / pip / 10, 1), 30.0) # 1:3 RR
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df_m5.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_bollinger_rsi(df, df_h1, symbol):
    res = BacktestResult("Bollinger+RSI Micro-Scalper")
    
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    bb_dev = 2.1 if "EUR" in symbol else 1.9
    df['sma_20'] = df['close'].rolling(20).mean()
    df['std_20'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['sma_20'] + (df['std_20'] * bb_dev)
    df['bb_lower'] = df['sma_20'] - (df['std_20'] * bb_dev)
    
    tr = pd.concat([df['high'] - df['low'], abs(df['high'] - df['close'].shift()), abs(df['low'] - df['close'].shift())], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    up_move = df['high'] - df['high'].shift(1)
    down_move = df['low'].shift(1) - df['low']
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_adx = tr.ewm(alpha=1/14, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/14, adjust=False).mean() / atr_adx)
    minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/14, adjust=False).mean() / atr_adx)
    dx = 100 * (np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9))
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    pip = 0.01 if "JPY" in symbol else 0.0001
    last_signal_time = None
    
    for i in range(100, len(df)-50):
        curr, prev = df.iloc[i], df.iloc[i-1]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        if "EUR" in symbol and (h >= 1 and h < 19): continue
        elif "GBP" in symbol and (h < 3 or h >= 13): continue
            
        if prev['adx'] > 45.0: continue
        
        trend_h1 = get_h1_trend(df_h1, curr['time'])
        cuerpo = abs(prev['close'] - prev['open'])
        lower_wick = prev['open'] - prev['low'] if prev['open'] < prev['close'] else prev['close'] - prev['low']
        upper_wick = prev['high'] - prev['close'] if prev['open'] < prev['close'] else prev['high'] - prev['open']
        
        signal = None
        if prev['rsi'] <= 32.0 and (prev['close'] <= prev['bb_lower'] or prev['low'] <= prev['bb_lower']):
            if lower_wick > (cuerpo * 0.8) and trend_h1 != -1: signal = "BUY"
        elif prev['rsi'] >= 68.0 and (prev['close'] >= prev['bb_upper'] or prev['high'] >= prev['bb_upper']):
            if upper_wick > (cuerpo * 0.8) and trend_h1 != 1: signal = "SELL"
                
        if signal:
            if last_signal_time == prev['time']: continue
            last_signal_time = prev['time']
            atr_pips = prev['atr'] / pip / 10
            sl = max(round(atr_pips * 1.5, 1), 8.0)
            tp = max(round(atr_pips * 2.0, 1), 15.0)
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

def sim_evergreen_pullback(df_m15, df_h1, symbol):
    res = BacktestResult("Evergreen Trend Pullback (M15)")
    
    # Calculate M15 EMA 50
    df_m15['ema_50'] = df_m15['close'].ewm(span=50, adjust=False).mean()
    
    pip = 1.0 if "US100" in symbol or "NAS" in symbol else (0.01 if "JPY" in symbol else 0.0001)
    
    for i in range(50, len(df_m15)-10):
        curr = df_m15.iloc[i]
        h = (pd.Timestamp(curr['time']).hour - 5) % 24
        
        # Avoid extreme illiquid hours (17:00 NY roll)
        if h == 17: continue
        
        # Check H1 Trend
        trend = get_h1_trend(df_h1, curr['time'])
        if trend == 0: continue
        
        signal = None
        # Bullish Pullback
        if trend == 1:
            if curr['low'] <= curr['ema_50'] and curr['close'] > curr['ema_50'] and df_m15.iloc[i-1]['close'] > df_m15.iloc[i-1]['ema_50']:
                signal = "BUY"
        # Bearish Pullback
        elif trend == -1:
            if curr['high'] >= curr['ema_50'] and curr['close'] < curr['ema_50'] and df_m15.iloc[i-1]['close'] < df_m15.iloc[i-1]['ema_50']:
                signal = "SELL"
                
        if signal:
            sl = 15.0
            tp = 20.0 # 1:1.33 RR
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df_m15.iloc[i+1:i+50].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_brainforge_v3(df, symbol):
    res = BacktestResult("BrainForge V3 (Institucional)")
    model_path = f"ai_lab/models/brain_v3.pkl"
    if not os.path.exists(model_path):
        return res
        
    try:
        model = joblib.load(model_path)
        if hasattr(model, 'set_params'):
            model.set_params(device="cpu")
    except Exception as e:
        print(f"  [ERROR] Fallo al cargar BrainForge V3: {e}")
        return res

    # Feature Engineering V3 Exacto
    PIP_SIZE = 0.0001 if "JPY" not in symbol else 0.01
    
    df['hour'] = df['time'].dt.hour
    df['day_of_week'] = df['time'].dt.dayofweek
    
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    
    df['dist_ema9_21_pips'] = (df['ema9'] - df['ema21']) / PIP_SIZE
    df['dist_close_ema50_pips'] = (df['close'] - df['ema50']) / PIP_SIZE
    df['dist_close_sma200_pips'] = (df['close'] - df['sma200']) / PIP_SIZE
    
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))
        
    df['rsi14'] = calc_rsi(df['close'], 14)
    rsi_min = df['rsi14'].rolling(14).min()
    rsi_max = df['rsi14'].rolling(14).max()
    df['stoch_rsi'] = (df['rsi14'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr14_pips'] = tr.rolling(window=14, min_periods=1).mean() / PIP_SIZE
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = (ema12 - ema26) / PIP_SIZE
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bbw'] = (std20 * 4) / sma20
    df['zscore20'] = (df['close'] - sma20) / (std20 + 1e-9)
    
    df['roc_15'] = df['close'].pct_change(15) * 100
    df['roc_30'] = df['close'].pct_change(30) * 100
    
    df['return_1_pips'] = df['close'].diff(1) / PIP_SIZE
    df['return_3_pips'] = df['close'].diff(3) / PIP_SIZE
    df['return_5_pips'] = df['close'].diff(5) / PIP_SIZE
    
    features_list = [
        'tick_volume', 'spread',
        'hour', 'day_of_week', 
        'ema9', 'ema21', 'ema50', 'sma200',
        'dist_ema9_21_pips', 'dist_close_ema50_pips', 'dist_close_sma200_pips',
        'rsi14', 'stoch_rsi', 'atr14_pips', 
        'macd', 'macd_signal', 'macd_hist', 
        'bbw', 'zscore20', 
        'roc_15', 'roc_30',
        'return_1_pips', 'return_3_pips', 'return_5_pips'
    ]
    
    df = df.dropna(subset=features_list)
    if len(df) == 0: return res
    
    for i in range(100, len(df)-50):
        curr = df.iloc[i]
        h = curr['hour']
        
        X_live = df[features_list].iloc[i:i+1]
        try:
            probs = model.predict_proba(X_live)[0]
            prob_win = probs[2]
        except:
            continue
            
        if prob_win >= 0.25: # Umbral óptimo de V3
            signal = "BUY" # El modelo V3 asume clase 2 como victoria (generalmente largo en nuestro contexto)
            sl = 20.0
            tp = 40.0
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

def sim_brainforge_v5(df, symbol):
    res = BacktestResult("BrainForge V5 LSTM (Institucional)")
    import torch
    import torch.nn as nn
    
    class LSTMBrainNet(nn.Module):
        def __init__(self, input_size, hidden_size=32, num_layers=1, num_classes=3, dropout=0.5):
            super(LSTMBrainNet, self).__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers
            self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
            self.fc1 = nn.Linear(hidden_size, 16)
            self.relu = nn.ReLU()
            self.dropout = nn.Dropout(dropout)
            self.fc2 = nn.Linear(16, num_classes)
            
        def forward(self, x):
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            out, _ = self.lstm(x, (h0, c0))
            out = out[:, -1, :] 
            out = self.fc1(out)
            out = self.relu(out)
            out = self.dropout(out)
            out = self.fc2(out)
            return out
            
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_lab', 'models'))
    model_path = os.path.join(base_dir, 'brain_v5_lstm.pth')
    scaler_path = os.path.join(base_dir, 'scaler_v5.pkl')
    
    if not os.path.exists(model_path) or not os.path.exists(scaler_path):
        return res
        
    try:
        scaler = joblib.load(scaler_path)
        device = torch.device('cpu') 
        model = LSTMBrainNet(input_size=29)
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
        model.eval()
    except Exception as e:
        print(f"  [ERROR] Fallo al cargar BrainForge V5: {e}")
        return res

    PIP_SIZE = 0.0001
    
    # 1. Variables cíclicas de tiempo
    hours = df['time'].dt.hour + (df['time'].dt.minute / 60.0)
    df['hour_sin'] = np.sin(2 * np.pi * hours / 24.0)
    df['hour_cos'] = np.cos(2 * np.pi * hours / 24.0)
    days = df['time'].dt.dayofweek
    df['day_sin'] = np.sin(2 * np.pi * days / 5.0)
    df['day_cos'] = np.cos(2 * np.pi * days / 5.0)
    
    # 2. Medias y distancias relativas
    ema9 = df['close'].ewm(span=9, adjust=False).mean()
    ema21 = df['close'].ewm(span=21, adjust=False).mean()
    ema50 = df['close'].ewm(span=50, adjust=False).mean()
    sma200 = df['close'].rolling(200).mean()
    ema_H1_50 = df['close'].ewm(span=200, adjust=False).mean()
    sma_H4_200 = df['close'].rolling(3200).mean()
    
    df['dist_ema9_21_pips'] = (ema9 - ema21) / PIP_SIZE
    df['dist_close_ema50_pips'] = (df['close'] - ema50) / PIP_SIZE
    df['dist_close_sma200_pips'] = (df['close'] - sma200) / PIP_SIZE
    df['dist_macro_H1_pips'] = (df['close'] - ema_H1_50) / PIP_SIZE
    df['dist_macro_H4_pips'] = (df['close'] - sma_H4_200) / PIP_SIZE
    
    # 3. Osciladores
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))
        
    df['rsi14'] = calc_rsi(df['close'], 14)
    rsi_min = df['rsi14'].rolling(14).min()
    rsi_max = df['rsi14'].rolling(14).max()
    df['stoch_rsi'] = (df['rsi14'] - rsi_min) / (rsi_max - rsi_min + 1e-9)
    
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr14_pips'] = tr.rolling(window=14, min_periods=1).mean() / PIP_SIZE
    
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = (ema12 - ema26) / PIP_SIZE
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bbw'] = (std20 * 4) / sma20
    df['zscore20'] = (df['close'] - sma20) / (std20 + 1e-9)
    
    df['roc_15'] = df['close'].pct_change(15) * 100
    df['roc_30'] = df['close'].pct_change(30) * 100
    
    df['return_1_pips'] = df['close'].diff(1) / PIP_SIZE
    df['return_3_pips'] = df['close'].diff(3) / PIP_SIZE
    df['return_5_pips'] = df['close'].diff(5) / PIP_SIZE
    
    # 4. Price Action SMC
    df['body_size_pips'] = (df['close'] - df['open']).abs() / PIP_SIZE
    df['candle_dir'] = np.where(df['close'] >= df['open'], 1, -1)
    df['upper_wick_pips'] = (df['high'] - df[['open', 'close']].max(axis=1)) / PIP_SIZE
    df['lower_wick_pips'] = (df[['open', 'close']].min(axis=1) - df['low']) / PIP_SIZE
    total_range = (df['high'] - df['low']) / PIP_SIZE
    df['wick_rejection_ratio'] = (df['upper_wick_pips'] + df['lower_wick_pips']) / (total_range + 1e-9)
    
    features_list = [
        'tick_volume', 'spread',
        'hour_sin', 'hour_cos', 'day_sin', 'day_cos', 
        'dist_ema9_21_pips', 'dist_close_ema50_pips', 'dist_close_sma200_pips',
        'dist_macro_H1_pips', 'dist_macro_H4_pips',
        'rsi14', 'stoch_rsi', 'atr14_pips', 
        'macd', 'macd_signal', 'macd_hist', 
        'bbw', 'zscore20', 
        'roc_15', 'roc_30',
        'return_1_pips', 'return_3_pips', 'return_5_pips',
        'body_size_pips', 'candle_dir', 'upper_wick_pips', 
        'lower_wick_pips', 'wick_rejection_ratio'
    ]
    
    df = df.dropna(subset=features_list)
    if len(df) == 0: return res
    
    seq_length = 60
    
    for i in range(seq_length + 50, len(df)-50):
        curr = df.iloc[i]
        h = curr['time'].hour
        
        X_live = df[features_list].iloc[i-seq_length+1:i+1].values
        
        if len(X_live) != seq_length: continue
        
        try:
            X_scaled = scaler.transform(X_live)
            X_tensor = torch.tensor(X_scaled, dtype=torch.float32).unsqueeze(0).to(device)
            with torch.no_grad():
                outputs = model(X_tensor)
                probs = torch.softmax(outputs, dim=1)[0]
                prob_win = probs[2].item()
        except:
            continue
            
        if prob_win >= 0.40: # Umbral Sniper V5 40%
            signal = "BUY"
            sl = 20.0
            tp = 40.0
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res


def sim_brainforge_qlearning(symbol="EURUSD"):
    res = BacktestResult("BrainForge Q-Learning V4 (Dueling-DRQN)")
    if symbol != "EURUSD": return res
    import onnxruntime as ort
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ai_lab'))
    model_path = os.path.join(base_dir, 'models', 'brain_qlearning_v4.onnx')
    data_path = os.path.join(base_dir, 'data', 'processed', f'{symbol}_M15_features.parquet')
    
    if not os.path.exists(model_path) or not os.path.exists(data_path):
        return res
        
    session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
    input_name = session.get_inputs()[0].name
    
    df = pd.read_parquet(data_path)
    
    features = [c for c in df.columns if c not in ['time', 'target']]
    if len(features) != 33:
        return res
        
    df = df.dropna(subset=features)
    df = df.iloc[-2000:]
    if len(df) < 20: return res
    
    import numpy as np
    
    position = 0
    entry_price = 0.0
    PIP_SIZE = 0.0001
    COMMISSION_PER_LOT = 7.0
    
    for i in range(10, len(df)):
        window = df[features].iloc[i-10:i].values
        state = window.astype(np.float32).reshape(1, 10, 33)
        
        q_values = session.run(None, {input_name: state})[0][0]
        action = np.argmax(q_values)
        
        curr = df.iloc[i]
        price = curr['close']
        hour = pd.Timestamp(curr['time']).hour
        
        # Training Actions: 0=Hold, 1=Buy, 2=Sell, 3=Close
        if action == 1 and position <= 0:
            if position == -1:
                pnl = (entry_price - price) / PIP_SIZE * 10.0 - COMMISSION_PER_LOT
                res.add_trade(pnl, hour, "SELL", 0, 0)
            position = 1
            entry_price = price
        elif action == 1 and position >= 0:
            if position == 1:
                pnl = (price - entry_price) / PIP_SIZE * 10.0 - COMMISSION_PER_LOT
                res.add_trade(pnl, hour, "BUY", 0, 0)
            position = -1
            entry_price = price
        elif action == 3 and position != 0:
            if position == 1:
                pnl = (price - entry_price) / PIP_SIZE * 10.0 - COMMISSION_PER_LOT
                res.add_trade(pnl, hour, "BUY", 0, 0)
            elif position == -1:
                pnl = (entry_price - price) / PIP_SIZE * 10.0 - COMMISSION_PER_LOT
                res.add_trade(pnl, hour, "SELL", 0, 0)
            position = 0
            entry_price = 0.0
            
    return res

def run_backtest(symbol="EURUSD", days=365, z=2.5, adx=45):
    if not mt5.initialize(): 
        print("❌ Error: MetaTrader 5 no está abierto o no pudo conectar.")
        return []
        
    mt5.symbol_select(symbol, True)
    
    # Intentar traer datos, los brokers de fondeo a veces solo dan 3 a 6 meses de historial M5
    r_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, days*24*12)
    r_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days*24*4)
    r_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, days*24 + 200)
    
    mt5.shutdown()
    
    if r_m5 is None or r_m15 is None or r_h1 is None:
        print(f"❌ ERROR CRÍTICO: Tu MetaTrader (FTMO) no tiene {days} días de historial para {symbol}.")
        print("💡 Solución: El broker bloquea descargas tan grandes de golpe. Intenta con --days 60 o --days 90 en el archivo RUN_BACKTEST.bat")
        return []
        
    m5 = pd.DataFrame(r_m5)
    m15 = pd.DataFrame(r_m15)
    h1 = pd.DataFrame(r_h1)
    
    for d in [m5, m15, h1]: 
        if 'time' in d.columns:
            d['time'] = pd.to_datetime(d['time'], unit='s')
            
    if 'close' in h1.columns:
        h1['close_ema_200'] = h1['close'].ewm(span=200, adjust=False).mean()

    # ═══════ SELECCIÓN ESTRATÉGICA POR SÍMBOLO ═══════
    if symbol == "EURUSD":
        # EURUSD: Especialista Tendencial y Sniper AI
        results = [
            sim_ttm_squeeze(m15.copy(), h1, symbol),
            sim_brainforge_v5(m15.copy(), symbol),
            sim_brainforge_qlearning(symbol)
        ]
    elif symbol == "GBPUSD":
        # GBPUSD: Desactivado por alta volatilidad
        results = []
    elif symbol == "US100.cash" or symbol == "NAS100":
        results = []
    else:
        results = []
    print(f"\n{'='*100}")
    print(f"  [+] {symbol} - REPORTE OPERATIVO (ESTRATEGIAS ACTIVAS)")
    print(f"{'='*100}")
    for r in results:
        rep = r.get_report()
        pf_str = f"PF:{rep['profit_factor']:.2f}" if rep['profit_factor'] else "PF:N/A"
        wr_str = f"WR:{rep['win_rate']}%" if rep['win_rate'] else "WR:N/A"
        print(f"  {rep['name']:40s} | T:{rep['trades']:3d} | {wr_str:>8} | {pf_str:>7} | PnL:${rep['total_pnl']:+8.2f} | DD:${rep['max_drawdown']:,.2f} | {rep['verdict']}")
    return [r.get_report() for r in results]
    
def sim_xgboost_ai(df, df_h1, symbol):
    res = BacktestResult("XGBoost AI (GPU Model)")
    model_path = f"data/rf_model_{symbol}.pkl"
    if not os.path.exists(model_path):
        print(f"  [ERROR] No se encontró el cerebro IA en {model_path}")
        return res
        
    try:
        model = joblib.load(model_path)
        if hasattr(model, 'set_params'):
            model.set_params(device="cpu")
    except Exception as e:
        print(f"  [ERROR] Fallo al cargar modelo: {e}")
        return res

    # Feature Engineering (Nasdaq Scale)
    df['hour'] = df['time'].dt.hour
    df['day_of_week'] = df['time'].dt.dayofweek
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_dist'] = df['ema20'] - df['ema50']
    
    # Z-Score
    sma50 = df['close'].rolling(50).mean()
    std50 = df['close'].rolling(50).std()
    df['zscore'] = (df['close'] - sma50) / (std50 + 1e-9)

    # ATR
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    df['atr'] = tr.rolling(14).mean()
    
    # ADX
    plus_dm = (df['high'] - df['high'].shift(1)).clip(lower=0)
    minus_dm = (df['low'].shift(1) - df['low']).clip(lower=0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)
    atr_adx = tr.ewm(alpha=1/14, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
    minus_di = 100 * (minus_dm.ewm(alpha=1/14, adjust=False).mean() / (atr_adx + 1e-10))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)) * 100
    df['adx'] = dx.ewm(alpha=1/14, adjust=False).mean()
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    df['volatility'] = df['high'] - df['low']
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Retorno
    df['return_last_3'] = df['close'] - df['close'].shift(3)
    
    features = ['hour', 'day_of_week', 'ema_dist', 'volatility', 'rsi', 'return_last_3', 'zscore', 'atr', 'adx', 'macd_hist']
    df = df.dropna(subset=features)
    if len(df) == 0: return res
    
    pip = 1.0 if "US100" in symbol or "NAS" in symbol else (0.01 if "JPY" in symbol else 0.0001)
    
    for i in range(100, len(df)-50):
        curr = df.iloc[i]
        h = curr['hour']
        
        # Filtro de horario Nasdaq (Solo operar en apertura NY y horas de alta liquidez)
        if h < 8 or h > 16: continue 
        
        X_live = df[features].iloc[i:i+1]
        try:
            pred = model.predict(X_live)[0]
        except:
            continue
            
        signal = None
        if pred == 2: signal = "BUY"
        elif pred == 0: signal = "SELL"
        
        if signal:
            # Filtro Tendencia HTF (Simulación del CIO Oracle)
            trend = get_h1_trend(df_h1, curr['time'])
            if (signal == "BUY" and trend == -1) or (signal == "SELL" and trend == 1):
                res.filtered += 1
                continue
                
            # SL y TP dinámicos
            tr = max(curr['high'] - curr['low'], abs(curr['high'] - df.iloc[i-1]['close']), abs(curr['low'] - df.iloc[i-1]['close']))
            atr_pips = tr / pip / 10
            if atr_pips < 5: atr_pips = 10
            
            if "US100" in symbol or "NAS" in symbol:
                sl = 20.0
                tp = 40.0
            else:
                sl = max(20.0, round(atr_pips * 1.5, 1))
                tp = max(40.0, round(atr_pips * 3.0, 1))
            
            pnl = calculate_pnl(signal, curr['close'], sl, tp, df.iloc[i+1:i+100].to_dict('records'), symbol)
            res.add_trade(pnl, h, signal, sl, tp)
            
    return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
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
