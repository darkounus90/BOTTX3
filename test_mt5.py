import MetaTrader5 as mt5
import time

def run_tests():
    print("=== INICIANDO PRUEBAS DE CONEXION MT5 ===")
    
    print("\n[Prueba 1] initialize() normal sin argumentos...")
    if mt5.initialize():
        print("EXITO: Prueba 1 funciono.")
        mt5.shutdown()
        return True
    else:
        print(f"FALLO: Prueba 1. Error: {mt5.last_error()}")
        
    print("\n[Prueba 2] initialize() con path explicito...")
    path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    if mt5.initialize(path=path):
        print("EXITO: Prueba 2 funciono.")
        mt5.shutdown()
        return True
    else:
        print(f"FALLO: Prueba 2. Error: {mt5.last_error()}")
        
    print("\n[Prueba 3] initialize() en Modo Portable...")
    if mt5.initialize(path=path, portable=True):
        print("EXITO: Prueba 3 funciono.")
        mt5.shutdown()
        return True
    else:
        print(f"FALLO: Prueba 3. Error: {mt5.last_error()}")
        
    print("\n[Prueba 4] initialize() con timeout extendido...")
    if mt5.initialize(timeout=120000):
        print("EXITO: Prueba 4 funciono.")
        mt5.shutdown()
        return True
    else:
        print(f"FALLO: Prueba 4. Error: {mt5.last_error()}")

    print("\n=== TODAS LAS PRUEBAS FALLARON ===")
    return False

if __name__ == "__main__":
    run_tests()
