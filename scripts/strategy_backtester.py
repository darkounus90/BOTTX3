"""
📊 TX3 PRO BOT - BACKTESTER CUANTITATIVO DE ESTRATEGIAS
=========================================================
Simula TODAS las estrategias del bot contra datos históricos reales de MT5.
Genera un veredicto frío: cuáles ganan, cuáles pierden, cuáles sobran.

Uso:
    python scripts/strategy_backtester.py
    python scripts/strategy_backtester.py --days 90 --symbol EURUSD
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
    pip_in_points = pip_size * 10  # Para pares de 5 dígitos, no se usa, pero pip_size es lo correcto
    
    sl_price_dist = sl_pips * pip_size
    tp_price_dist = tp_pips * pip_size
    slippage_dist = SLIPPAGE_PIPS * pip_size
    spread_dist   = SPREAD_PIPS_SIM * pip_size
    
    # Ajustar entrada por spread
    if direction == "BUY":
        effective_entry = entry_price + spread_dist
        sl_price = effective_entry - sl_price_dist
        tp_price = effective_entry + tp_price_dist
    else:
        effective_entry = entry_price - spread_dist
        sl_price = effective_entry + sl_price_dist
        tp_price = effective_entry - tp_price_dist
    
    # Simular vela por vela
    for candle in future_candles:
        if direction == "BUY":
            # ¿Tocó el SL primero? (Low penetró el SL)
            if candle["low"] <= sl_price:
                loss_pips = sl_pips + SLIPPAGE_PIPS + SPREAD_PIPS_SIM
                # Riesgo monetario proporcional
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return -risk_usd  # Pérdida completa del riesgo
            # ¿Tocó el TP?
            if candle["high"] >= tp_price:
                reward_ratio = tp_pips / sl_pips
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return risk_usd * reward_ratio - COMMISSION_PER_LOT * 0.1  # Ganancia proporcional
        else:  # SELL
            if candle["high"] >= sl_price:
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return -risk_usd
            if candle["low"] <= tp_price:
                reward_ratio = tp_pips / sl_pips
                risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
                return risk_usd * reward_ratio - COMMISSION_PER_LOT * 0.1
    
    # Si no tocó ni SL ni TP en las velas disponibles, cerramos al último precio
    last_close = future_candles[-1]["close"] if len(future_candles) > 0 else entry_price
    if direction == "BUY":
        pips_result = (last_close - effective_entry) / pip_size
    else:
        pips_result = (effective_entry - last_close) / pip_size
    
    risk_usd = INITIAL_BALANCE * (RISK_PER_TRADE_PCT / 100)
    return (pips_result / sl_pips) * risk_usd - COMMISSION_PER_LOT * 0.05


def sim_bollinger_rsi(df, symbol):
    """Simula la estrategia Bollinger + RSI sobre el DataFrame histórico"""
    result = BacktestResult("Bollinger+RSI Reversion")
    
    bb_period = 20
    bb_dev = 1.8
    rsi_period = 14
    rsi_ob = 65.0
    rsi_os = 35.0
    adx_threshold = 45.0
    
    # Calcular indicadores
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
    
    # ADX simplificado
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    tr_smooth = tr.rolling(window=14).sum()
    plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/14).mean() / (tr_smooth + 1e-9))
    dx = (abs(plus_di - minus_di) / (abs(plus_di + minus_di) + 1e-9)) * 100
    df['adx'] = dx.ewm(alpha=1/14).mean()
    
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    
    # Iterar velas
    for i in range(bb_period + 20, len(df) - 50):
        row = df.iloc[i]
        
        if pd.isna(row['bb_upper']) or pd.isna(row['rsi']) or pd.isna(row['adx']) or pd.isna(row['atr']):
            continue
        if row['adx'] > adx_threshold:
            continue
        
        signal = None
        if row['close'] < row['bb_lower'] and row['rsi'] < rsi_os:
            signal = "BUY"
        elif row['close'] > row['bb_upper'] and row['rsi'] > rsi_ob:
            signal = "SELL"
        
        if not signal:
            continue
        
        atr_val = row['atr']
        point = pip_size / 10
        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 2.5) / (10 * point), 1)
        sl_pips = max(sl_pips, 20)
        tp_pips = max(tp_pips, 40)
        
        future = df.iloc[i+1:i+50].to_dict('records')
        pnl = calculate_pnl(signal, row['close'], sl_pips, tp_pips, future, symbol)
        
        hour_est = (pd.Timestamp(row['time']).hour - 5) % 24  # Aproximación broker GMT+2 -> EST
        result.add_trade(pnl, hour_est, signal, sl_pips, tp_pips)
    
    return result


def sim_ema_cross(df, symbol):
    """Simula la estrategia Dynamic Momentum Pro (EMA Cross + MACD + Pullback)"""
    result = BacktestResult("Dynamic Momentum Pro (EMA Cross)")
    
    ema_fast = 20
    ema_slow = 50
    ema_trend_period = 200
    adx_threshold = 18
    
    df['ema_fast'] = df['close'].ewm(span=ema_fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=ema_slow, adjust=False).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift(1))
    low_close = abs(df['low'] - df['close'].shift(1))
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(window=14).mean()
    
    # ADX
    plus_dm = df['high'].diff()
    minus_dm = df['low'].diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    tr_smooth = true_range.rolling(window=14).sum()
    plus_di = 100 * (plus_dm.ewm(alpha=1/14).mean() / (tr_smooth + 1e-9))
    minus_di = 100 * (abs(minus_dm).ewm(alpha=1/14).mean() / (tr_smooth + 1e-9))
    dx = (abs(plus_di - minus_di) / (abs(plus_di + minus_di) + 1e-9)) * 100
    df['adx'] = dx.ewm(alpha=1/14).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss_s = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss_s.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    macd_fast = df['close'].ewm(span=12, adjust=False).mean()
    macd_slow = df['close'].ewm(span=26, adjust=False).mean()
    df['macd_line'] = macd_fast - macd_slow
    df['macd_signal'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd_line'] - df['macd_signal']
    
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    
    for i in range(ema_slow + 5, len(df) - 50):
        prev = df.iloc[i]
        prev2 = df.iloc[i-1]
        
        if pd.isna(prev['adx']) or pd.isna(prev['atr']) or pd.isna(prev['rsi']):
            continue
        if prev['adx'] < adx_threshold:
            continue
        
        uptrend = prev['ema_fast'] > prev['ema_slow']
        downtrend = prev['ema_fast'] < prev['ema_slow']
        
        bullish_cross = uptrend and (prev2['ema_fast'] <= prev2['ema_slow'])
        bearish_cross = downtrend and (prev2['ema_fast'] >= prev2['ema_slow'])
        
        bullish_pullback = uptrend and (prev2['close'] < prev2['ema_fast']) and (prev['close'] > prev['ema_fast']) and (40 < prev['rsi'] < 70)
        bearish_pullback = downtrend and (prev2['close'] > prev2['ema_fast']) and (prev['close'] < prev['ema_fast']) and (30 < prev['rsi'] < 60)
        
        macd_bull = prev['macd_hist'] > 0 and prev['macd_line'] > prev['macd_signal']
        macd_bear = prev['macd_hist'] < 0 and prev['macd_line'] < prev['macd_signal']
        
        signal = None
        if (bullish_cross or bullish_pullback) and macd_bull:
            signal = "BUY"
        elif (bearish_cross or bearish_pullback) and macd_bear:
            signal = "SELL"
        
        if not signal:
            continue
        
        atr_val = prev['atr']
        point = pip_size / 10
        sl_pips = round((atr_val * 1.5) / (10 * point), 1)
        tp_pips = round((atr_val * 3.0) / (10 * point), 1)
        sl_pips = max(sl_pips, 20)
        tp_pips = max(tp_pips, 40)
        
        future = df.iloc[i+1:i+50].to_dict('records')
        pnl = calculate_pnl(signal, prev['close'], sl_pips, tp_pips, future, symbol)
        
        hour_est = (pd.Timestamp(prev['time']).hour - 5) % 24
        result.add_trade(pnl, hour_est, signal, sl_pips, tp_pips)
    
    return result


def sim_session_breakout(df_m15, symbol, session_name, valid_hours_est, min_body_pips=5.0, range_limit=None, need_h4_trend=False, df_h4=None):
    """
    Simulador genérico de Breakout de Sesión.
    Aplica la misma lógica que tus 4 estrategias de breakout.
    """
    result = BacktestResult(f"{session_name} Breakout")
    
    pip_mult = 100 if "JPY" in symbol else 10000
    pip_size = 0.01 if "JPY" in symbol else 0.0001
    
    # Calcular tendencia H4 si aplica
    h4_trend_series = None
    if need_h4_trend and df_h4 is not None and len(df_h4) >= 50:
        h4_ema_50 = df_h4['close'].ewm(span=50, adjust=False).mean()
        h4_trend_series = pd.Series(
            np.where(df_h4['close'] > h4_ema_50, "BULLISH", "BEARISH"),
            index=df_h4.index
        )
    
    last_trade_day = None
    
    for i in range(20, len(df_m15) - 50):
        candle = df_m15.iloc[i]
        
        if pd.isna(candle['time']):
            continue
        
        candle_time = pd.Timestamp(candle['time'])
        hour_est = (candle_time.hour - 5) % 24
        day_str = candle_time.strftime("%Y-%m-%d")
        
        # Filtro de horario
        if hour_est not in valid_hours_est:
            continue
        
        # Solo 1 trade por día para breakouts
        if last_trade_day == day_str:
            continue
        
        # Rango de 16 velas previas (4 horas en M15)
        lookback = df_m15.iloc[i-16:i]
        range_high = lookback['high'].max()
        range_low = lookback['low'].min()
        rango_pips = (range_high - range_low) * pip_mult
        
        # Filtro de rango máximo (si aplica, como London que usa 30 pips)
        if range_limit and rango_pips > range_limit:
            continue
        
        # Tamaño de cuerpo de la vela
        body_size = abs(candle['close'] - candle['open']) * pip_mult
        total_size = abs(candle['high'] - candle['low']) * pip_mult
        decisive = (body_size / max(total_size, 0.001)) >= 0.6
        
        signal = None
        
        # Breakout Alcista
        if candle['close'] > range_high and candle['open'] < range_high:
            passes_body = body_size > min_body_pips
            passes_decisive = decisive if session_name == "NY" else True
            if passes_body and passes_decisive:
                if need_h4_trend:
                    if h4_trend_series is not None:
                        # Buscar la tendencia H4 más reciente
                        h4_idx = df_h4.index[df_h4['time'] <= candle['time']].max() if len(df_h4[df_h4['time'] <= candle['time']]) > 0 else None
                        if h4_idx is not None and h4_trend_series.iloc[h4_idx] == "BULLISH":
                            signal = "BUY"
                    # Si no hay data H4, skip
                else:
                    signal = "BUY"
        
        # Breakout Bajista
        elif candle['close'] < range_low and candle['open'] > range_low:
            min_sell_body = 2.5 if session_name == "NY" else 3.0
            passes_body = body_size > min_sell_body
            passes_decisive = decisive if session_name == "NY" else True
            if passes_body and passes_decisive:
                if need_h4_trend:
                    if h4_trend_series is not None:
                        h4_idx = df_h4.index[df_h4['time'] <= candle['time']].max() if len(df_h4[df_h4['time'] <= candle['time']]) > 0 else None
                        if h4_idx is not None and h4_trend_series.iloc[h4_idx] == "BEARISH":
                            signal = "SELL"
                else:
                    signal = "SELL"
        
        if not signal:
            continue
        
        last_trade_day = day_str
        
        # ATR para SL/TP
        hl = df_m15['high'] - df_m15['low']
        atr = hl.rolling(14).mean().iloc[i]
        if pd.isna(atr) or atr <= 0:
            continue
        
        point = pip_size / 10
        sl_mult = 1.5 if session_name in ("London", "Tokyo", "Sydney") else 2.0
        tp_mult = 3.5 if session_name in ("London", "Tokyo", "Sydney") else 3.0
        
        sl_pips = round((atr * sl_mult) / (10 * point), 1)
        tp_pips = round((atr * tp_mult) / (10 * point), 1)
        sl_pips = max(sl_pips, 20)
        tp_pips = max(tp_pips, 40)
        
        future = df_m15.iloc[i+1:i+50].to_dict('records')
        pnl = calculate_pnl(signal, candle['close'], sl_pips, tp_pips, future, symbol)
        result.add_trade(pnl, hour_est, signal, sl_pips, tp_pips)
    
    return result


# ═══════════════════════════════════════════════════════════════
#  MOTOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def run_backtest(symbol="EURUSD", days=60):
    """Ejecuta el backtest completo de todas las estrategias"""
    
    print("=" * 70)
    print(f"📊 TX3 PRO - BACKTESTER CUANTITATIVO DE ESTRATEGIAS")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Símbolo: {symbol} | Período: {days} días")
    print("=" * 70)
    
    if not mt5.initialize():
        print("❌ Error: No se pudo inicializar MT5.")
        return
    
    # ─── Descargar data histórica ──────────────────────────────
    print(f"\n[*] Descargando {days} días de velas M5 de {symbol}...")
    m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, days * 24 * 12)  # 12 velas/hora en M5
    if m5_rates is None or len(m5_rates) < 500:
        print(f"❌ Error: No hay suficiente data M5 para {symbol}.")
        mt5.shutdown()
        return
    df_m5 = pd.DataFrame(m5_rates)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
    print(f"    ✅ {len(df_m5):,} velas M5 descargadas ({df_m5.iloc[0]['time']} → {df_m5.iloc[-1]['time']})")
    
    print(f"\n[*] Descargando {days} días de velas M15 de {symbol}...")
    m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, days * 24 * 4)  # 4 velas/hora en M15
    if m15_rates is None or len(m15_rates) < 200:
        print(f"❌ Error: No hay suficiente data M15 para {symbol}.")
        mt5.shutdown()
        return
    df_m15 = pd.DataFrame(m15_rates)
    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
    print(f"    ✅ {len(df_m15):,} velas M15 descargadas")
    
    print(f"\n[*] Descargando data H4 para filtro de tendencia...")
    h4_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, days * 6)
    df_h4 = None
    if h4_rates is not None and len(h4_rates) >= 50:
        df_h4 = pd.DataFrame(h4_rates)
        df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
        print(f"    ✅ {len(df_h4):,} velas H4 descargadas")
    else:
        print(f"    ⚠️ Data H4 insuficiente. London Breakout no tendrá filtro de tendencia.")
    
    mt5.shutdown()
    
    # ─── Ejecutar cada estrategia ──────────────────────────────
    results = []
    
    print(f"\n{'─' * 70}")
    print(f"[*] Simulando: Bollinger+RSI Reversion...")
    r1 = sim_bollinger_rsi(df_m5.copy(), symbol)
    results.append(r1)
    print(f"    → {r1.wins + r1.losses} trades simulados")
    
    print(f"[*] Simulando: Dynamic Momentum Pro (EMA Cross)...")
    r2 = sim_ema_cross(df_m5.copy(), symbol)
    results.append(r2)
    print(f"    → {r2.wins + r2.losses} trades simulados")
    
    print(f"[*] Simulando: NY Opening Breakout...")
    r3 = sim_session_breakout(df_m15.copy(), symbol, "NY",
                               valid_hours_est=list(range(3, 7)),   # 8-11 AM EST -> broker hrs
                               min_body_pips=4.0)
    results.append(r3)
    print(f"    → {r3.wins + r3.losses} trades simulados")
    
    print(f"[*] Simulando: London Opening Breakout...")
    r4 = sim_session_breakout(df_m15.copy(), symbol, "London",
                               valid_hours_est=list(range(22, 24)) + list(range(0, 2)),  # 3-7 AM EST -> broker hrs
                               min_body_pips=8.0,
                               range_limit=30.0,
                               need_h4_trend=True,
                               df_h4=df_h4)
    results.append(r4)
    print(f"    → {r4.wins + r4.losses} trades simulados")
    
    print(f"[*] Simulando: Tokyo Opening Breakout...")
    r5 = sim_session_breakout(df_m15.copy(), symbol, "Tokyo",
                               valid_hours_est=list(range(14, 17)),   # 19:00-2:00 AM EST -> broker hrs
                               min_body_pips=5.0)
    results.append(r5)
    print(f"    → {r5.wins + r5.losses} trades simulados")
    
    print(f"[*] Simulando: Sydney Opening Breakout...")
    r6 = sim_session_breakout(df_m15.copy(), symbol, "Sydney",
                               valid_hours_est=list(range(12, 14)),  # 17-19 EST -> broker hrs
                               min_body_pips=5.0)
    results.append(r6)
    print(f"    → {r6.wins + r6.losses} trades simulados")
    
    # ─── REPORTE FINAL ─────────────────────────────────────────
    reports = [r.get_report() for r in results]
    
    # Ordenar por P&L total (de mayor a menor)
    reports.sort(key=lambda x: x.get("total_pnl", 0), reverse=True)
    
    print(f"\n{'═' * 70}")
    print(f"📈 VEREDICTO CUANTITATIVO - RANKING DE ESTRATEGIAS ({symbol})")
    print(f"{'═' * 70}")
    
    for idx, rep in enumerate(reports, 1):
        print(f"\n{'─' * 60}")
        print(f"  #{idx} {rep['name']}")
        print(f"{'─' * 60}")
        
        if rep["trades"] == 0:
            print(f"    ⚠️ Sin trades detectados en el período")
            continue
        
        pnl_icon = "🟢" if rep.get("total_pnl", 0) >= 0 else "🔴"
        
        print(f"    Trades:            {rep['trades']} ({rep['wins']}W / {rep['losses']}L)")
        print(f"    Win Rate:          {rep['win_rate']}%")
        print(f"    Profit Factor:     {rep['profit_factor']}")
        print(f"    Expectancy:        ${rep['expectancy_usd']}/trade")
        print(f"    P&L Total:         {pnl_icon} ${rep['total_pnl']:+,.2f}")
        print(f"    Max Drawdown:      ${rep['max_drawdown']:,.2f}")
        print(f"    Mejor Trade:       ${rep['best_trade']:+,.2f}")
        print(f"    Peor Trade:        ${rep['worst_trade']:+,.2f}")
        print(f"    Avg Win / Avg Loss: ${rep['avg_win']:,.2f} / ${rep['avg_loss']:,.2f}")
        print(f"    Max Rachas Perdidas: {rep['max_consecutive_losses']}")
        if rep.get("best_hour_est") is not None:
            print(f"    Mejor Hora (EST):  {rep['best_hour_est']}:00 ({rep['best_hour_winrate']}% WR)")
        print(f"    ┌─────────────────────────────────┐")
        print(f"    │ VEREDICTO: {rep['verdict']:>22s} │")
        print(f"    └─────────────────────────────────┘")
    
    # ─── RESUMEN EJECUTIVO ─────────────────────────────────────
    keeps = [r for r in reports if r.get("verdict_code") == "KEEP"]
    optimizes = [r for r in reports if r.get("verdict_code") == "OPTIMIZE"]
    disables = [r for r in reports if r.get("verdict_code") == "DISABLE"]
    
    print(f"\n{'═' * 70}")
    print(f"🏆 RESUMEN EJECUTIVO")
    print(f"{'═' * 70}")
    print(f"  🟢 MANTENER ({len(keeps)}):    {', '.join(r['name'] for r in keeps) or 'Ninguna'}")
    print(f"  🟡 OPTIMIZAR ({len(optimizes)}):  {', '.join(r['name'] for r in optimizes) or 'Ninguna'}")
    print(f"  🔴 DESACTIVAR ({len(disables)}): {', '.join(r['name'] for r in disables) or 'Ninguna'}")
    
    total_pnl = sum(r.get("total_pnl", 0) for r in reports)
    print(f"\n  💰 P&L Combinado Total: ${total_pnl:+,.2f}")
    print(f"  📊 Período analizado: {days} días")
    print(f"{'═' * 70}")
    
    # Guardar JSON para análisis posterior
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backtest_results.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "symbol": symbol,
            "days": days,
            "date": datetime.now().isoformat(),
            "strategies": reports
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 Resultados guardados en: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TX3 Strategy Backtester")
    parser.add_argument("--days", type=int, default=60, help="Días de historia a analizar (default: 60)")
    parser.add_argument("--symbol", type=str, default="EURUSD", help="Símbolo a analizar (default: EURUSD)")
    args = parser.parse_args()
    
    run_backtest(symbol=args.symbol, days=args.days)
