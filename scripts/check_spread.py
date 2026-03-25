import MetaTrader5 as mt5

def check():
    mt5.initialize()
    for sym in ["EURUSD", "GBPUSD"]:
        info = mt5.symbol_info(sym)
        if info:
            print(f"--- {sym} ---")
            print(f"Spread int: {info.spread}")
            print(f"Digits: {info.digits}")
            print(f"Point: {info.point}")
            print(f"Actual Bid: {info.bid}")
            print(f"Actual Ask: {info.ask}")
            print(f"Ask - Bid: {info.ask - info.bid:.6f}")
            print(f"(Ask-Bid)/Point: {(info.ask - info.bid) / info.point:.1f}")
check()
