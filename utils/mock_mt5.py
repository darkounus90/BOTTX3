import yfinance as yf
import pandas as pd
import numpy as np
import time

# Constantes de MetaTrader 5
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_H1 = 16385
TIMEFRAME_D1 = 16408

def last_error():
    return (1, "Success")

def initialize(*args, **kwargs):
    return True

def shutdown():
    pass

class DummyAccount:
    def __init__(self):
        self.login = 999999
        self.server = "YahooFinance-AI-Advisor"
        self.name = "Modo Asesor IA"
        self.balance = 50000.0
        self.equity = 50000.0
        self.margin = 0.0
        self.margin_free = 50000.0
        self.margin_level = 100.0
        self.profit = 0.0
        self.leverage = 100
        self.company = "Yahoo Finance AI"
        self.trade_allowed = True
        self.margin_so_mode = 0
        self.margin_so_call = 50.0
        self.margin_so_so = 30.0

def history_deals_get(*args, **kwargs):
    return ()

def positions_get(*args, **kwargs):
    return ()

def orders_get(*args, **kwargs):
    return ()

class DummyTerminalInfo:
    def __init__(self):
        self.connected = True
        self.trade_allowed = True
        self.build = 5735

def terminal_info():
    return DummyTerminalInfo()

def account_info():
    return DummyAccount()

class DummySymbolInfo:
    def __init__(self):
        self.visible = True
        self.trade_mode = 4 # Full access

def symbol_info(symbol):
    return DummySymbolInfo()

def symbol_select(symbol, enable):
    return True

def _translate_symbol(symbol):
    if "NAS100" in symbol or "US100" in symbol:
        return "NQ=F"
    if symbol == "EURUSD":
        return "EURUSD=X"
    if symbol == "GBPUSD":
        return "GBPUSD=X"
    if "XAUUSD" in symbol or "GOLD" in symbol:
        return "GC=F"
    return symbol + "=X"

def copy_rates_from_pos(symbol, timeframe, start_pos, count):
    yf_sym = _translate_symbol(symbol)
    
    # Mapear timeframe de MT5 a yfinance
    if timeframe == TIMEFRAME_M1:
        interval = "1m"
    elif timeframe == TIMEFRAME_M5:
        interval = "5m"
    elif timeframe == TIMEFRAME_M15:
        interval = "15m"
    elif timeframe == TIMEFRAME_H1:
        interval = "1h"
    else:
        interval = "1d"
        
    try:
        df = yf.download(tickers=yf_sym, interval=interval, period="60d", progress=False)
        if df.empty:
            return None
            
        # Si count > len(df), limitarlo
        if count > len(df):
            count = len(df)
            
        # Tomar los últimos 'count' registros
        df = df.iloc[-count:].copy()
        
        # yfinance devuelve MultiIndex columnas si bajas un solo ticker a veces, o flat. Aplanar por las dudas.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Construir el array estructurado que espera MT5
        dtype = [
            ('time', 'i8'), ('open', 'f8'), ('high', 'f8'), 
            ('low', 'f8'), ('close', 'f8'), ('tick_volume', 'i8'), 
            ('spread', 'i4'), ('real_volume', 'i8')
        ]
        
        records = np.zeros(len(df), dtype=dtype)
        records['time'] = df.index.astype('int64') // 10**9
        records['open'] = df['Open'].values
        records['high'] = df['High'].values
        records['low'] = df['Low'].values
        records['close'] = df['Close'].values
        records['tick_volume'] = df.get('Volume', np.zeros(len(df))).values
        records['spread'] = np.zeros(len(df))
        records['real_volume'] = np.zeros(len(df))
        
        return records
    except Exception as e:
        print(f"Error mock yfinance para {symbol}: {e}")
        return None

def symbol_info_tick(symbol):
    class DummyTick:
        pass
        
    rates = copy_rates_from_pos(symbol, TIMEFRAME_M1, 0, 1)
    if rates is None or len(rates) == 0:
        return None
        
    tick = DummyTick()
    tick.bid = float(rates['close'][0])
    tick.ask = float(rates['close'][0])
    tick.time = int(time.time())
    return tick

# Añadir propiedades dummy para engañar a MetaTrader5.__version__
__version__ = "5.0.0.AI_ADVISOR"
