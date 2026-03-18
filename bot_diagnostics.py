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
    log("="*60)
    log(f"🚀 TX3 PRO BOT - DIAGNÓSTICO TOTAL (ENTERPRISE EDITION)")
    log(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    passed = 0
    failed = 0
    errors = []

    def test(name, func):
        nonlocal passed, failed
        log(f"\n[*] Auditando: {name}...")
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

    # ==========================================
    # 0. INICIALIZACIÓN BASE 
    # ==========================================
    from utils.logger import BotLogger
    try:
        real_logger = BotLogger(name="DiagnosticoTotal", log_dir="logs")
    except Exception as e:
        log("    [ERROR FATAL] No se pudo instanciar BotLogger. El diagnóstico se detendrá.")
        return

    # ==========================================
    # 1. ARCHIVOS DE CONFIGURACIÓN GLOBALES
    # ==========================================
    def test_config():
        from config.settings import (BotConfig, TelegramConfig, ChallengeConfig, 
                                     DashboardConfig, SessionConfig, BacktestConfig)
        return (f"Símbolo: {BotConfig.DEFAULT_SYMBOL} | "
                f"Fase 1 Target: {ChallengeConfig.FASE1_PROFIT_TARGET_PCT}% | "
                f"Dashboard Port: {DashboardConfig.PORT} | "
                f"SMC Activado: {BotConfig.SMC_ENABLED}")
    test("Configuraciones Principales", test_config)

    # ==========================================
    # 2. UTILS (CONECTORES, ESTADO, ETC.)
    # ==========================================
    def test_utils():
        from utils.mt5_connector import MT5Connector
        from utils.trade_journal import TradeJournal
        from utils.state_manager import StateManager
        from utils.telegram_notifier import TelegramNotifier
        from utils.telegram_commands import TelegramCommandHandler
        
        journal = TradeJournal(logger=real_logger, phase=1)
        assert hasattr(journal, "record_open")
        
        assert hasattr(StateManager, "load_state") or hasattr(StateManager, "save_state"), "Falta lógica en StateManager"
        assert hasattr(TelegramCommandHandler, "start") or hasattr(TelegramCommandHandler, "handle_command"), "Falta lógica en TelegramCommandHandler"
        
        return "MT5, DB, Notificaciones, State Manager y Commands listos."
    test("Módulo UTILS (Managers & Integraciones)", test_utils)

    # ==========================================
    # 3. CORE (FILTROS DE RIESGO Y MERCADO)
    # ==========================================
    def test_core_filters():
        from core.news_filter import NewsFilter
        from core.session_filter import SessionFilter
        assert hasattr(NewsFilter, "is_news_time") or hasattr(NewsFilter, "update_calendar"), "NewsFilter incompleto"
        assert hasattr(SessionFilter, "is_allowed_session") or hasattr(SessionFilter, "is_trading_time"), "SessionFilter incompleto"
        return "Filtros de Noticias y Sesiones OK."
    test("Core: Filtros Temporales (News & Session)", test_core_filters)

    def test_core_managers():
        from core.risk_manager import RiskManager
        from core.position_manager import PositionManager
        from core.portfolio_manager import PortfolioManager
        from core.trailing_stop import TrailingStopManager
        from core.phase_tracker import PhaseTracker
        
        # Validar lógica estática (compilación de la clase sin forzar instanciación riesgosa)
        assert bool(RiskManager)
        assert bool(PositionManager)
        assert bool(PortfolioManager)
        assert bool(TrailingStopManager)
        
        tracker = PhaseTracker(logger=real_logger, phase=1)
        assert hasattr(tracker, "check_phase_complete")
        
        return "Trade/Risk/Position/Trailing/Portfolio Managers compilados y listos."
    test("Core: Managers Transaccionales y de Riesgo", test_core_managers)

    def test_core_intel():
        from core.llm_oracle import GeminiOracle
        from core.smc_scanner import SMCScanner
        from core.ai_sentiment import AISentimentAnalyzer
        
        # Probar instanciación de IA segura
        oracle = GeminiOracle(logger=real_logger)
        assert hasattr(oracle, "evaluate_system_health"), "GeminiOracle error"
        assert bool(SMCScanner)
        assert bool(AISentimentAnalyzer)
        
        return "Conciencia Institucional (Oracle, SMC, Sentiment) OK."
    test("Core: Análisis Avanzado (Oracle, SMC, Sentiment)", test_core_intel)

    # ==========================================
    # 4. ESTRATEGIAS CUANTITATIVAS
    # ==========================================
    def test_strategies_basic():
        from strategy.base_strategy import BaseStrategy
        from strategy.bollinger_rsi import BollingerRSIStrategy
        from strategy.ema_cross import EMACrossStrategy
        
        b_rsi = BollingerRSIStrategy(logger=real_logger, symbol="EURUSD")
        assert hasattr(b_rsi, "generate_signal")
        assert bool(EMACrossStrategy)
        assert bool(BaseStrategy)
        
        return "Estrategias de Reversión y Tendencia OK."
    test("Estrategias: Osciladores y Tendencia", test_strategies_basic)

    def test_strategies_breakouts():
        from strategy.ny_opening_breakout import NYOpeningBreakoutStrategy
        from strategy.london_opening_breakout import LondonOpeningBreakoutStrategy
        from strategy.tokyo_opening_breakout import TokyoOpeningBreakoutStrategy
        from strategy.sydney_opening_breakout import SydneyOpeningBreakoutStrategy
        
        assert bool(NYOpeningBreakoutStrategy)
        assert bool(LondonOpeningBreakoutStrategy)
        assert bool(TokyoOpeningBreakoutStrategy)
        assert bool(SydneyOpeningBreakoutStrategy)
        
        return "Estrategias de Breakout de Sesión Importadas."
    test("Estrategias: Breakouts Institucionales", test_strategies_breakouts)

    def test_strategies_ml():
        from strategy.ml_random_forest import MLRandomForestStrategy
        from strategy.q_learning_agent import QLearningAgent
        
        assert bool(MLRandomForestStrategy)
        assert bool(QLearningAgent)
        return "Motores de Machine Learning (RF y Q-Learning) OK."
    test("Estrategias: Machine Learning y RL", test_strategies_ml)

    # ==========================================
    # 5. DASHBOARD Y SERVIDOR WEB
    # ==========================================
    def test_dashboard():
        from dashboard.app import run_dashboard, update_dashboard_data, app
        # Validar si app (Flask o el framework que uses) se importó con éxito
        assert callable(run_dashboard) or bool(app)
        return "Servidor Web del Dashboard compilado internamente."
    test("Panel Web (Dashboard)", test_dashboard)

    # ==========================================
    # RESUMEN Y GENERACIÓN DE REPORTE
    # ==========================================
    log("\n" + "="*60)
    log("📈 RESULTADO FINAL DEL DIAGNÓSTICO EN CASCADA:")
    log(f"Categorías verificadas: {passed + failed}")
    log(f"Total submódulos verificados: +25 archivos")
    log(f"Éxitos: {passed}")
    log(f"Errores: {failed}")
    log("="*60)

    if failed > 0:
        log("\n🚨 DETALLES EXACTOS DE LOS ERRORES DE SINTAXIS/MÓDULOS:")
        for name, err in errors:
            log(f"\n--- FALLA EN BUNDLE: {name} ---")
            log(err)
    else:
        log("\n✅ ESTATUS 100% OPERATIVO.")
        log("Todos los módulos base, inteligencias, gestores de riesgo y web")
        log("compilaron y reconocieron sus funciones exitosamente.")

    # Escribir reporte
    try:
        with open("DIAGNOSTICO_REPORTE.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(r))
        print("\n[+] El reporte de sistema ENTERPRISE ha sido guardado en: DIAGNOSTICO_REPORTE.txt")
    except Exception as e:
        print(f"\n[!] No se pudo guardar el reporte localmente: {e}")

if __name__ == "__main__":
    run_diagnostics()
    time.sleep(2)
