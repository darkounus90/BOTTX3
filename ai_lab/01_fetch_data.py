import os
import sys
import time
import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def fetch_data(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15, bars=100000):
    print(f"🚀 Iniciando Data Pipeline para {symbol}")
    
    # Intentar inicializar (asumimos que la terminal ya está abierta o la ruta por defecto sirve)
    if not mt5.initialize():
        print(f"❌ Error al conectar con MetaTrader 5: {mt5.last_error()}")
        return False
        
    print(f"✅ Conectado a MT5 (Broker: {mt5.terminal_info().company})")
    
    # Seleccionar símbolo
    if not mt5.symbol_select(symbol, True):
        print(f"❌ Símbolo {symbol} no encontrado.")
        mt5.shutdown()
        return False
        
    print(f"📥 Descargando historial de {symbol} año por año (2015-2026)...")
    
    all_rates = []
    
    for year in range(2015, 2027):
        # MT5 requiere fechas en formato ingenuo (naive) que asumen la zona horaria del servidor
        date_from = datetime(year, 1, 1)
        date_to = datetime(year, 12, 31, 23, 59) if year < 2026 else datetime.now()
        
        rates = mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
        
        if rates is not None and len(rates) > 0:
            all_rates.append(pd.DataFrame(rates))
            print(f"  ✅ {year}: {len(rates):,} velas")
        else:
            print(f"  ⚠️ {year}: Sin datos.")

    if not all_rates:
        print("❌ No se descargaron datos en absoluto.")
        mt5.shutdown()
        return False
        
    print(f"✅ Descarga completada. Consolidando datos...")
    
    # Consolidar todos los años
    df = pd.concat(all_rates, ignore_index=True)
    
    # 🕒 NORMALIZACIÓN TEMPORAL (UTC)
    # MT5 devuelve 'time' como un timestamp POSIX (segundos desde 1970).
    df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
    
    # Filtrar columnas esenciales y limpiar duplicados (por solapamiento)
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread']]
    df = df.drop_duplicates(subset=['time']).sort_values('time').reset_index(drop=True)
    
    # Guardar en parquet
    output_dir = os.path.join(os.path.dirname(__file__), "data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, f"{symbol}_M15.parquet")
    df.to_parquet(output_path, index=False, compression='snappy')
    
    print(f"💾 Datos guardados de forma estéril y comprimida en: {output_path}")
    print(f"   Total Velas: {len(df):,}")
    print(f"   Primer registro: {df['time'].iloc[0]}")
    print(f"   Último registro: {df['time'].iloc[-1]}")
    
    mt5.shutdown()
    return True

if __name__ == "__main__":
    fetch_data(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15)
