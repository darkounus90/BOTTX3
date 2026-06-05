import MetaTrader5 as mt5
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os
import sys
import time

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def inicializar_mt5():
    print("⏳ Limpiando puertos... (Cerrando MetaTrader 5)")
    os.system("taskkill /F /IM terminal64.exe >nul 2>&1")
    time.sleep(3) # Esperar a que se libere la memoria RAM
    
    ruta_mt5 = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
    print("⏳ Iniciando y conectando MetaTrader 5 desde cero...")
    
    if not mt5.initialize(path=ruta_mt5, timeout=60000):
        print("❌ Error crítico al inicializar MT5:", mt5.last_error())
        return False
        
    print("🚀 Conexión con MetaTrader 5 establecida con éxito.")
    print(f"   Broker detectado en terminal: {mt5.terminal_info().company}")
    return True

def pre_cargar_simbolo(simbolo, timeframe):
    """
    Fuerza al servidor del broker a enviar el histórico a la caché local
    para asegurar que copy_rates_range traiga las velas completas.
    """
    fecha_hoy = datetime.now()
    fecha_antigua = fecha_hoy - timedelta(days=3750) # ~10 años atrás (2016)
    
    # Peticiones de ráfaga para despertar el canal de datos del activo
    mt5.copy_rates_from(simbolo, timeframe, fecha_hoy, 50)
    mt5.copy_rates_from(simbolo, timeframe, fecha_antigua, 50)
    time.sleep(1.5)

def descargar_todo():
    # --- CONFIGURACIÓN DE LA ARQUITECTURA BOTTX3 ---
    simbolos = ["US100.cash", "EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
    timeframes = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1
    }
    
    anio_inicio = 2016
    anio_fin = 2026
    ruta_base = "data/raw"
    os.makedirs(ruta_base, exist_ok=True)
    # -----------------------------------------------
    
    for sim in simbolos:
        # Forzar que el símbolo esté activo y visible en el Market Watch
        if not mt5.symbol_select(sim, True):
            print(f"\n⚠️ Símbolo '{sim}' no disponible en tu Broker. Revisa si en FTMO se llama diferente (ej: US100). Saltando...")
            continue
            
        for tf_nombre, tf_constante in timeframes.items():
            print(f"\n📥 Sincronizando e indexando: {sim} [{tf_nombre}]")
            pre_cargar_simbolo(sim, tf_constante)
            
            for anio in range(anio_inicio, anio_fin + 1):
                fecha_ini = datetime(anio, 1, 1, 0, 0)
                # Si es el año actual (2026), descargar hasta el día de hoy
                fecha_fin = datetime(anio, 12, 31, 23, 59) if anio < 2026 else datetime.now()
                
                # Extracción del bloque anual indexado
                rates = mt5.copy_rates_range(sim, tf_constante, fecha_ini, fecha_fin)
                
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    df['time'] = pd.to_datetime(df['time'], unit='s')
                    
                    # Filtrado estricto de columnas cuantitativas primarias
                    columnas_esenciales = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread']
                    df = df[columnas_esenciales]
                    
                    # Nomenclatura exacta solicitada: data/raw/EURUSD_M5_2016.parquet
                    nombre_archivo = f"{sim}_{tf_nombre}_{anio}.parquet"
                    ruta_completa = os.path.join(ruta_base, nombre_archivo)
                    
                    # Almacenamiento binario de alta velocidad
                    df.to_parquet(ruta_completa, index=False, compression='snappy')
                    print(f"  ✅ Año {anio} guardado: {len(df):,} velas -> {nombre_archivo}")
                else:
                    print(f"  ❌ El servidor no devolvió barras para {sim} {tf_nombre} en el año {anio}.")

def descargar_con_yfinance():
    print("⚠️ Fallback activado: Descargando datos masivos desde Yahoo Finance...")
    ruta_base = "data/raw"
    os.makedirs(ruta_base, exist_ok=True)
    
    mapa = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X",
        "XAUUSD": "GC=F",
        "NAS100": "NQ=F"
    }
    
    for sim_mt5, sim_yf in mapa.items():
        print(f"\n📥 Sincronizando Yahoo Finance: {sim_mt5} (H1)")
        try:
            df = yf.download(sim_yf, period="730d", interval="1h", progress=False)
            if df is not None and not df.empty:
                df = df.reset_index()
                # Aplanar las columnas MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]
                
                df['time'] = df['Datetime'].dt.tz_localize(None)
                df = df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'tick_volume'})
                df['spread'] = 0
                
                columnas_esenciales = ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread']
                df = df[columnas_esenciales]
                
                nombre_archivo = f"{sim_mt5}_H1_2024.parquet"
                ruta_completa = os.path.join(ruta_base, nombre_archivo)
                df.to_parquet(ruta_completa, index=False, compression='snappy')
                print(f"  ✅ Descargado fallback: {len(df):,} velas -> {nombre_archivo}")
            else:
                print(f"  ❌ No hay datos para {sim_yf}")
        except Exception as e:
            print(f"  ❌ Error descargando {sim_mt5}: {e}")

if __name__ == "__main__":
    if inicializar_mt5():
        descargar_todo()
    else:
        descargar_con_yfinance()
    print("\n🎉 FASE 2 COMPLETADA: Datos base particionados guardados en data/raw/")