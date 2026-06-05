import MetaTrader5 as mt5
import time

print("Intentando engancharse al MetaTrader que el usuario abrio...")
print("Usando MetaTrader5 version:", mt5.__version__)

# Intento 1: Sin argumentos (Busca la instancia activa)
start_time = time.time()
if mt5.initialize(timeout=10000):
    print("EXITO: Se conecto a la instancia activa!")
    print("Cuenta:", mt5.account_info().login)
    mt5.shutdown()
else:
    print("FALLO (Sin argumentos):", mt5.last_error())
    
# Intento 2: Con ruta explicita
print("\nIntentando con ruta explicita...")
path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if mt5.initialize(path=path, timeout=10000):
    print("EXITO: Se conecto con ruta explicita!")
    print("Cuenta:", mt5.account_info().login)
    mt5.shutdown()
else:
    print("FALLO (Ruta explicita):", mt5.last_error())
