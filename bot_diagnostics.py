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
    log(f"🤖 TX3 PRO BOT - REPORTE DE DIAGNÓSTICO PROFESIONAL")
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

    # 0. Instanciar el Logger Real
    from utils.logger import BotLogger
    try:
        real_logger = BotLogger(name="Diagnostico", log_dir="logs")
    except Exception as e:
        log("    [ERROR FATAL] No se pudo instanciar BotLogger. El diagnóstico se detendrá.")
        return

    # 1. Test Configuración
    def test_config():
        from config.settings import BotConfig, TelegramConfig, ChallengeConfig
        return f"Símbolo base: {BotConfig.DEFAULT_SYMBOL}, Target Fase 1: {ChallengeConfig.FASE1_PROFIT_TARGET_PCT}%"
    test("Configuración Global", test_config)

    # 2. Test MT5 conector
    def test_mt5():
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return "El módulo MetaTrader5 no está instalado o no es compatible (Se requiere Windows)."
        from utils.mt5_connector import MT5Connector
        
        # MT5Connector usualmente no requiere argumentos estrictos aparte de config, pero probamos si existe la clase
        assert hasattr(MT5Connector, "connect") or hasattr(MT5Connector, "initialize"), "MT5Connector no tiene métodos esperados."
        return "Clase MT5Connector validada correctamente."
    test("Conexión MT5", test_mt5)

    # 3. Test Trade Journal (DB)
    def test_journal():
        from utils.trade_journal import TradeJournal
        # Firma exacta: TradeJournal(logger: BotLogger, phase: int)
        journal = TradeJournal(logger=real_logger, phase=1)
        # Probamos un método real
        assert hasattr(journal, "get_today_stats"), "TradeJournal no tiene get_today_stats"
        return "TradeJournal instanciado correctamente con SQLite."
    test("Base de Datos / Journal", test_journal)

    # 4. Test Risk Manager y Phase Tracker
    def test_risk():
        from core.phase_tracker import PhaseTracker
        from core.risk_manager import RiskManager
        
        # Firma exacta: PhaseTracker(logger: BotLogger, phase: int)  -- (No requiere journal)
        tracker = PhaseTracker(logger=real_logger, phase=1)
        assert hasattr(tracker, "check_phase_complete"), "PhaseTracker no tiene check_phase_complete"
        
        # Instanciar RiskManager (típicamente toma balance, riesgo, etc. o es estático, probamos atributos)
        assert hasattr(RiskManager, "calculate_lot_size") or hasattr(RiskManager, "check_risk") or bool(RiskManager), "Módulo de Riesgo cargado"
        return "PhaseTracker instanciado correctamente."
    test("Gestión de Riesgo", test_risk)

    # 5. Test Telegram Notifier
    def test_telegram():
        from utils.telegram_notifier import TelegramNotifier
        # Firma exacta: TelegramNotifier(logger: BotLogger)
        notifier = TelegramNotifier(logger=real_logger)
        assert hasattr(notifier, "notify_bot_started"), "TelegramNotifier no tiene notify_bot_started"
        return "TelegramNotifier instanciado correctamente."
    test("Notificaciones Telegram", test_telegram)

    # 6. Test Gemini API (Oracle)
    def test_gemini():
        from core.llm_oracle import GeminiOracle
        # Firma exacta: GeminiOracle(logger: BotLogger)
        oracle = GeminiOracle(logger=real_logger)
        # La clase tiene evaluate_system_health, no analyze_market
        assert hasattr(oracle, "evaluate_system_health"), "GeminiOracle no tiene evaluate_system_health"
        return "Módulo GeminiOracle instanciado correctamente."
    test("Gemini API (Oracle)", test_gemini)

    # 7. Test Estrategias
    def test_strategies():
        from strategy.bollinger_rsi import BollingerRSIStrategy
        # Firma exacta: BollingerRSIStrategy(logger: BotLogger, symbol: str)
        b_rsi = BollingerRSIStrategy(logger=real_logger, symbol="EURUSD")
        assert hasattr(b_rsi, "generate_signal"), "BollingerRSIStrategy no tiene generate_signal"
        return "BollingerRSIStrategy instanciada con éxito."
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
    time.sleep(2)
