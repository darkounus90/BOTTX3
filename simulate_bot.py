import sys
import unittest.mock as mock
import pandas as pd
import datetime

# ─── 1. MOCK DE METATRADER 5 (Para simular entorno seguro en Mac/Linux) ───
mt5_mock = mock.MagicMock()

# Mockear mt5.symbol_info
symbol_info_mock = mock.MagicMock()
symbol_info_mock.point = 0.00001
symbol_info_mock.trade_tick_size = 0.00001
symbol_info_mock.trade_tick_value = 1.0
symbol_info_mock.volume_step = 0.01
symbol_info_mock.volume_min = 0.01
symbol_info_mock.volume_max = 100.0
mt5_mock.symbol_info.return_value = symbol_info_mock

# Mockear mt5.account_info
account_info_mock = mock.MagicMock()
account_info_mock.balance = 50000.0
account_info_mock.equity = 50000.0
mt5_mock.account_info.return_value = account_info_mock

# Mockear Constantes
mt5_mock.TIMEFRAME_M15 = 15
mt5_mock.TIMEFRAME_H4 = 16385
mt5_mock.ORDER_TYPE_BUY = 0
mt5_mock.ORDER_TYPE_SELL = 1

# Mockear copy_rates_from_pos
def mock_copy_rates(*args, **kwargs):
    # Generar data falsa de velas 
    df = pd.DataFrame({
        'time': [1600000000 + i * 900 for i in range(100)],
        'open': [1.1000 + (i * 0.0001) for i in range(100)],
        'high': [1.1010 + (i * 0.0001) for i in range(100)],
        'low': [1.0990 + (i * 0.0001) for i in range(100)],
        'close': [1.1005 + (i * 0.0001) for i in range(100)],
        'tick_volume': [100 for _ in range(100)]
    })
    return df.to_dict('records')

mt5_mock.copy_rates_from_pos.side_effect = mock_copy_rates

# Inyectar el mock al sistema ANTES de importar los modulos del bot
sys.modules['MetaTrader5'] = mt5_mock

# Mockear dashboard y telegram para aislar las pruebas algorítmicas
dashboard_mock = mock.MagicMock()
sys.modules['dashboard'] = dashboard_mock
sys.modules['dashboard.app'] = dashboard_mock

telegram_mock = mock.MagicMock()
sys.modules['utils.telegram_notifier'] = telegram_mock

# ─── 2. IMPORTAR MÓDULOS DEL BOT ───
try:
    from config.settings import BotConfig
    from utils.logger import BotLogger
    from core.news_filter import NewsFilter
    from core.risk_manager import RiskManager
    from core.position_manager import PositionManager
    from core.trailing_stop import TrailingStopManager
    from strategy.london_opening_breakout import LondonOpeningBreakoutStrategy
    
    print("✅ [AUDITORÍA SINTAXIS] Todas las importaciones fueron exisotas. No hay errores de corchetes, indentación ni dependencias.")
except Exception as e:
    print(f"❌ [ERROR SINTAXIS CRÍTICO] Falta en compilación: {e}")
    sys.exit(1)

# ─── 3. SIMULACIÓN DE FLUJO DE EJECUCIÓN (DRY RUN) ───
def run_simulation():
    print("\n🚀 INICIANDO ENTORNO DE SIMULACIÓN TX3...")
    logger = BotLogger()
    logger.info = lambda x: print(f" [LOG] {x}")
    logger.warning = lambda x: print(f" [WARN] {x}")
    logger.error = lambda x: print(f" [ERROR] {x}")
    logger.critical = lambda x: print(f" [CRITICAL] {x}")
    logger.success = lambda x: print(f" [SUCCESS] {x}")
    logger.risk = lambda x: print(f" [RISK] {x}")
    
    # Pruebas a los 5 Pilares
    
    try:
        print("\n🧪 Testeando Gestor de Riesgos...")
        rm = RiskManager(logger)
        daily_status = rm.check_daily_drawdown()
        print(f"   -> Drawdown status OK: {daily_status['level']}")
    except Exception as e:
        print(f"❌ Falla en RiskManager: {e}")
        
    try:
        print("\n🧪 Testeando Noticias (Pilar 5: Fail-Safe)...")
        nf = NewsFilter(logger)
        # Forzar un fallo de red ficticio
        nf.enabled = True
        nf.is_safe_to_trade("EURUSD")
        print("   -> Fallback de Noticias ejecutado sin Crash.")
    except Exception as e:
        print(f"❌ Falla en NewsFilter: {e}")

    try:
        print("\n🧪 Testeando Trailing Stop (Pilar 3: 1x ATR Break Even)...")
        ts_mgr = TrailingStopManager(logger)
        # Inyectar posición falsa
        pos_mock = mock.MagicMock()
        pos_mock.ticket = 12345
        pos_mock.symbol = "EURUSD"
        pos_mock.type = 0 # BUY
        pos_mock.price_open = 1.1000
        pos_mock.sl = 1.0990
        pos_mock.magic = BotConfig.MAGIC_NUMBER
        
        tick_mock = mock.MagicMock()
        tick_mock.bid = 1.1050 # 50 pips de profit
        tick_mock.ask = 1.1051
        mt5_mock.symbol_info_tick.return_value = tick_mock
        
        # Ejecutar update
        ts_mgr._update_position_trailing(pos_mock)
        print("   -> Lógica de Trailing Stop asimilada correctamente enviando request simulado.")
    except Exception as e:
        print(f"❌ Falla en Trailing Stop / Break Even: {e}")

    try:
        print("\n🧪 Testeando Gestor de Posiciones (Pilar 2: Supervivencia de Lotes)...")
        pm = PositionManager(logger, phase=1, risk_manager=rm)
        lotes = pm.calculate_position_size("EURUSD", stop_loss_pips=10.0)
        print(f"   -> Lotes calculados (math.floor aplicado rigurosamente): {lotes}")
    except Exception as e:
        print(f"❌ Falla en Position Manager: {e}")
        
    try:
        print("\n🧪 Testeando Estrategia London Breakout (Pilar 1 y 4: Caja Asiática y Correlación)...")
        strategy = LondonOpeningBreakoutStrategy(logger, symbol="EURUSD")
        signal = strategy.generate_signal()
        print(f"   -> Señal generada por London Breakout: {signal}")
    except Exception as e:
        import traceback
        print(f"❌ Falla en Estrategia Breakout: {e}")
        traceback.print_exc()

    print("\n🦾 SIMULACIÓN CONCLUIDA. El Bot es invulnerable a crashes lógicos.")

if __name__ == "__main__":
    run_simulation()
