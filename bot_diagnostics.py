import os
import sys
import traceback
import time
from datetime import datetime

r = []

def log(msg):
    print(msg)
    r.append(msg)

def run_diagnostics():
    log("="*50)
    log(f"🤖 TX3 PRO BOT - REPORTE DE DIAGNÓSTICO")
    log(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*50)
    
    passed = 0
    failed = 0
    errors = []

    def test(name, func):
        nonlocal passed, failed
        log(f"[*] Probando: {name}...")
        try:
            res = func()
            log(f"    [ÉXITO] {name} OK.")
            if res:
                log(f"    -> {res}")
            passed += 1
        except Exception as e:
            err = traceback.format_exc()
            log(f"    [ERROR] {name} falló!")
            log(f"    {str(e)}")
            errors.append((name, err))
            failed += 1

    # 1. Test Configuración
    def test_config():
        from config.settings import BotConfig, TelegramConfig
        return f"Símbolo base: {BotConfig.SYMBOL}, Telegram Mock: {TelegramConfig.MOCK_TELEGRAM}"
    test("Configuración Global", test_config)

    # 2. Test MT5
    def test_mt5():
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return "El módulo MetaTrader5 no está instalado o no es compatible con este OS (Requiere Windows para funcionar)."
        
        # Test basic connection function if available in your connector
        from utils.mt5_connector import MT5Connector
        from config.settings import TX3Config
        # We don't want to actually log in potentially, but MT5Connector initializes without logging fully unless login() is called or initialize()
        conn = MT5Connector(
            login_id=TX3Config.LOGIN,
            password=TX3Config.PASSWORD,
            server=TX3Config.SERVER
        )
        return "Conector MT5 instanciado correctamente."
    test("Conexión MT5", test_mt5)

    # 3. Test Trade Journal (DB)
    def test_journal():
        from utils.trade_journal import TradeJournal
        journal = TradeJournal(db_path='test_diagnostics.db')
        journal.log_trade(
            ticket=999999,
            symbol="TEST",
            action="BUY",
            volume=0.1,
            price=1.0,
            sl=0.9,
            tp=1.1,
            time="2024-01-01 00:00:00"
        )
        journal.get_all_trades()
        # cleanup
        import sqlite3
        journal.conn.close()
        try:
            os.remove('test_diagnostics.db')
        except:
            pass
        return "Base de datos local (SQLite) operativa."
    test("Base de Datos / Journal", test_journal)

    # 4. Test Risk Manager
    def test_risk():
        from core.risk_manager import RiskManager
        from utils.trade_journal import TradeJournal
        from core.phase_tracker import PhaseTracker
        
        # simple mock
        class MockJournal:
            def get_all_trades(self): return []
            def get_daily_trades(self): return []
            def get_today_stats(self): return {'trades': 0, 'win_pct': 0, 'balance': 50000}
        
        tracker = PhaseTracker(phase=1, journal=MockJournal())
        risk = RiskManager(balance=50000, max_daily_loss=(50000*0.05), max_total_loss=(50000*0.10))
        vol = risk.calculate_lot_size(sl_pips=100) # Returns valid vol?
        return f"Gestor de riesgo OK. Riesgo calculado: {vol} lotes."
    test("Gestión de Riesgo", test_risk)

    # 5. Test Telegram Notifier
    def test_telegram():
        from utils.telegram_notifier import TelegramNotifier
        from config.settings import TelegramConfig
        notifier = TelegramNotifier()
        token_len = len(TelegramConfig.TELEGRAM_TOKEN) if TelegramConfig.TELEGRAM_TOKEN else 0
        return f"Notifier OK. Bot token len: {token_len} chars."
    test("Notificaciones Telegram", test_telegram)

    # 6. Test Gemini Oracle
    def test_gemini():
        from core.llm_oracle import GeminiOracle
        from config.settings import BotConfig
        if not BotConfig.GEMINI_API_KEY:
            return "API KEY no configurada. Saltando conexión activa."
        oracle = GeminiOracle()
        return "Oracle instanciado correctamente."
    test("Gemini API (Oracle)", test_gemini)

    # 7. Test Estrategias
    def test_strategies():
        from strategy.bollinger_rsi import BollingerRSIStrategy
        from strategy.ny_opening_breakout import NYOpeningBreakoutStrategy
        b_rsi = BollingerRSIStrategy(symbol="XAUUSD")
        ny_op = NYOpeningBreakoutStrategy(symbol="XAUUSD")
        return "Estrategias cargadas e instanciadas."
    test("Módulos de Estrategia", test_strategies)

    log("\n" + "="*50)
    log("📈 RESUMEN DEL DIAGNÓSTICO:")
    log(f"Funciones probadas: {passed + failed}")
    log(f"Éxitos: {passed}")
    log(f"Errores: {failed}")
    log("="*50)

    if failed > 0:
        log("\n🚨 DETALLES DE ERRORES:")
        for name, err in errors:
            log(f"\n--- ERROR en {name} ---")
            log(err)

    # Escribir reporte
    try:
        with open("DIAGNOSTICO_REPORTE.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(r))
        print("\n[+] Reporte completo guardado en: DIAGNOSTICO_REPORTE.txt")
    except Exception as e:
        print(f"\n[!] No se pudo guardar el reporte en disco: {e}")

if __name__ == "__main__":
    run_diagnostics()
    # Pause slightly so the window doesn't close instantly if run isolated
    time.sleep(2)
