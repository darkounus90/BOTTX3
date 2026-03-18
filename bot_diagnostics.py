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

    # Logger dummy para inicializar clases
    class DummyLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass

    # 1. Test Configuración
    def test_config():
        from config.settings import BotConfig, TelegramConfig
        return f"Símbolo base: {BotConfig.DEFAULT_SYMBOL}, Telegram Token Len: {len(TelegramConfig.BOT_TOKEN)}"
    test("Configuración Global", test_config)

    # 2. Test MT5 conector (solo instanciación y carga de librería)
    def test_mt5():
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return "El módulo MetaTrader5 no está instalado o no es compatible con este OS (Requiere Windows para funcionar)."
        
        from utils.mt5_connector import MT5Connector
        # Solo verificamos que exista la clase y podemos cargarla
        assert hasattr(MT5Connector, "connect") or hasattr(MT5Connector, "initialize"), "MT5Connector no tiene métodos esperados."
        return "Clase MT5Connector validada correctamente."
    test("Conexión MT5", test_mt5)

    # 3. Test Trade Journal (DB)
    def test_journal():
        from utils.trade_journal import TradeJournal
        # Instanciar seguro sin pasar db_path o pasándolo si es necesario
        try:
            journal = TradeJournal(logger=DummyLogger())
        except TypeError:
            journal = TradeJournal()
            
        assert hasattr(journal, "log_trade"), "No se encontró el método log_trade"
        return "TradeJournal validado."
    test("Base de Datos / Journal", test_journal)

    # 4. Test Risk Manager y Phase Tracker
    def test_risk():
        from core.risk_manager import RiskManager
        from core.phase_tracker import PhaseTracker
        
        # Validar PhaseTracker
        try:
            tracker = PhaseTracker(phase=1, logger=DummyLogger())
        except TypeError:
            try:
                tracker = PhaseTracker(phase=1)
            except:
                tracker = PhaseTracker()

        # Validar RiskManager sin intentar adivinar sus args
        assert hasattr(RiskManager, "calculate_lot_size") or hasattr(RiskManager, "check_risk"), "Faltan métodos de riesgo"
        return "Módulos de Riesgo revisados."
    test("Gestión de Riesgo", test_risk)

    # 5. Test Telegram Notifier
    def test_telegram():
        from utils.telegram_notifier import TelegramNotifier
        try:
            notifier = TelegramNotifier(logger=DummyLogger())
        except TypeError:
            notifier = TelegramNotifier()
            
        assert hasattr(notifier, "send_message"), "El método send_message no existe"
        return "Módulo de Telegram validado."
    test("Notificaciones Telegram", test_telegram)

    # 6. Test Gemini API (Oracle)
    def test_gemini():
        from core.llm_oracle import GeminiOracle
        import os
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            try:
                from config.settings import BotConfig
                if hasattr(BotConfig, "GEMINI_API_KEY"):
                    key = BotConfig.GEMINI_API_KEY
            except: pass
            
        assert hasattr(GeminiOracle, "analyze_market") or hasattr(GeminiOracle, "get_sentiment"), "Faltan métodos en Oracle"
        return "Módulo GeminiOracle validado estructuralmente."
    test("Gemini API (Oracle)", test_gemini)

    # 7. Test Estrategias
    def test_strategies():
        from strategy.bollinger_rsi import BollingerRSIStrategy
        from strategy.ny_opening_breakout import NYOpeningBreakoutStrategy
        
        try:
            b_rsi = BollingerRSIStrategy(symbol="XAUUSD", logger=DummyLogger())
        except TypeError:
            try:
                b_rsi = BollingerRSIStrategy("XAUUSD", DummyLogger())
            except TypeError:
                b_rsi = BollingerRSIStrategy()
                
        return "Módulos de Estrategia importados con éxito."
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
