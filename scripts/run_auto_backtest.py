"""
Script Wrapper para el Bucle Experimental Autónomo (AutoTrade)
Usado por el agente de IA para evaluar la estrategia que acaba de programar.
"""
import sys
import os
import importlib

# Ensure botalgo modules can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.engine import BacktestEngine
from utils.logger import BotLogger

def main():
    if len(sys.argv) < 2:
        print("❌ Uso: python3 run_auto_backtest.py <nombre_modulo_estrategia>")
        print("Ejemplo: python3 run_auto_backtest.py strategy.auto_mi_estrategia_v1")
        sys.exit(1)
        
    module_name = sys.argv[1]
    
    try:
        # Importación dinámica del módulo de estrategia que la IA acaba de crear
        strategy_module = importlib.import_module(module_name)
        
        # Buscar la primera clase en el módulo que herede de BaseStrategy
        from strategy.base_strategy import BaseStrategy
        StrategyClass = None
        for name, obj in strategy_module.__dict__.items():
            if isinstance(obj, type) and issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                StrategyClass = obj
                break
                
        if not StrategyClass:
            print(f"❌ Error: No se encontró una subclase de BaseStrategy en {module_name}")
            sys.exit(1)
            
        logger = BotLogger(name="AutoTest")
        strategy_instance = StrategyClass(logger=logger, symbol="EURUSD")
        
        # Instanciar el motor e inyectar la estrategia
        engine = BacktestEngine(strategy=strategy_instance, logger=logger, symbol="EURUSD", days=30)
        
        print(f"\n🚀 [AUTOTRADE LAB] Iniciando Backtest en {module_name}...")
        engine.run()
        print("\n✅ Backtest Finalizado. Analiza los resultados y procede con la siguiente iteración.")
        
    except ImportError as e:
        print(f"❌ Error de Importación: {e}. Probablemente la IA escribió mal el código de la estrategia.")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"❌ Error Crítico en el Backtest: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
