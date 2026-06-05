import pandas as pd
import glob
import os
import sys

def parse_histdata():
    print("🚀 Iniciando Motor de Ingesta Multi-Década (HistData)")
    histdata_dir = r"C:\Users\PC\Desktop\datos csv"
    # Buscar recursivamente todos los .csv en las subcarpetas
    csv_files = []
    for root, dirs, files in os.walk(histdata_dir):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(os.path.join(root, file))
    
    if not csv_files:
        print(f"❌ No se encontraron archivos CSV en {histdata_dir} o sus subcarpetas.")
        return
        
    print(f"📥 Procesando {len(csv_files)} archivos CSV de HistData...")
    
    df_list = []
    for f in csv_files:
        print(f"   Leyendo {os.path.basename(f)}...")
        # HistData ASCII M1 standard: "20140101 000000;1.374400;1.374400;1.374400;1.374400;0"
        try:
            df = pd.read_csv(f, header=None, sep=';', engine='python')
            if df.shape[1] < 6:
                df = pd.read_csv(f, header=None, sep=',', engine='python')
                
            # Solo tomar las primeras 6 columnas (por si hay basura al final)
            df = df.iloc[:, :6]
            df.columns = ['datetime', 'open', 'high', 'low', 'close', 'tick_volume']
            df_list.append(df)
        except Exception as e:
            print(f"   ❌ Error leyendo {os.path.basename(f)}: {e}")
        
    if not df_list:
        return
        
    df_master = pd.concat(df_list, ignore_index=True)
    
    print("\n🕒 Procesando marcas de tiempo (Moviendo de EST a UTC absoluto)...")
    # Formato de fecha HistData: "20140101 000000"
    df_master['datetime'] = pd.to_datetime(df_master['datetime'], format="%Y%m%d %H%M%S")
    
    # HistData entrega datos en hora EST (UTC-5) y NO usa Horario de Verano (No DST).
    # Por ende, el UTC absoluto es simplemente sumarle 5 horas.
    df_master['time'] = df_master['datetime'] + pd.Timedelta(hours=5)
    df_master['time'] = df_master['time'].dt.tz_localize('UTC')
    
    df_master = df_master.drop(columns=['datetime'])
    df_master = df_master.sort_values('time')
    
    print("🔄 Remuestreando millones de velas M1 a M15 institucional...")
    df_master.set_index('time', inplace=True)
    
    # Remuestreo de velas
    df_m15 = df_master.resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    })
    
    # Eliminar espacios vacíos (Fines de semana o huecos)
    df_m15 = df_m15.dropna()
    df_m15 = df_m15.reset_index()
    
    df_m15['spread'] = 0.0 # Valor simulado ya que HistData no incluye Spread
    
    output_path = os.path.join(os.path.dirname(__file__), "data", "raw", "EURUSD_M15.parquet")
    df_m15.to_parquet(output_path, index=False, compression='snappy')
    
    print(f"\n✅ ¡ÉXITO! Dataset M15 finalizado: {len(df_m15):,} velas consolidadas.")
    print(f"   Inicio: {df_m15['time'].iloc[0]}")
    print(f"   Fin:    {df_m15['time'].iloc[-1]}")
    print(f"\n💾 Guardado definitivo en: {output_path}")

if __name__ == '__main__':
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    parse_histdata()
