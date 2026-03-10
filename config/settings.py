"""
⚙️ TX3 Pro Challenge $50K - Configuración Central
===================================================
Todos los parámetros del challenge, bot, y servicios externos
en un solo lugar. Ningún valor mágico en el código.
"""

import os


class ChallengeConfig:
    """Configuración del 2 Phase Pro Challenge de $50,000"""

    # ─── INFORMACIÓN DE LA CUENTA ─────────────────────────────────────
    BALANCE_INICIAL = 50_000

    # ─── FASE 1 - Evaluación ──────────────────────────────────────────
    FASE1_PROFIT_TARGET = 4_000          # AJUSTADO: Add-on 8% Profit Target activo
    FASE1_PROFIT_TARGET_PCT = 8.0

    # ─── FASE 2 - Evaluación ──────────────────────────────────────────
    FASE2_PROFIT_TARGET = 2_500          # 5% de 50k
    FASE2_PROFIT_TARGET_PCT = 5.0

    # ─── DRAWDOWN LIMITS ──────────────────────────────────────────────
    MAX_DAILY_DRAWDOWN = 2_500           # 5% de 50k
    MAX_DAILY_DRAWDOWN_PCT = 5.0

    MAX_OVERALL_DRAWDOWN = 4_000         # AJUSTADO: Add-on 8% Max Loss activo
    MAX_OVERALL_DRAWDOWN_PCT = 8.0

    # ─── DÍAS MÍNIMOS ─────────────────────────────────────────────────
    MIN_TRADING_DAYS = 0                 # AJUSTADO: Add-on 'No Minimum Trading Days' activo
    MIN_PROFIT_PER_DAY = 250             # (Solo aplica si hubiera mínimo de días)

    # ─── FUNDED ACCOUNT ───────────────────────────────────────────────
    PROFIT_SPLIT = 90                    # AJUSTADO: Add-on '90/10 Profit Split' activo
    MIN_PAYOUT = 1_000
    CONSISTENCY_RULE_PCT = 40            # Máx 40% en un solo día

    @classmethod
    def get_profit_target(cls, phase: int) -> float:
        if phase == 1:
            return cls.FASE1_PROFIT_TARGET
        elif phase == 2:
            return cls.FASE2_PROFIT_TARGET
        raise ValueError(f"Fase inválida: {phase}")

    @classmethod
    def get_profit_target_pct(cls, phase: int) -> float:
        if phase == 1:
            return cls.FASE1_PROFIT_TARGET_PCT
        elif phase == 2:
            return cls.FASE2_PROFIT_TARGET_PCT
        raise ValueError(f"Fase inválida: {phase}")


class BotConfig:
    """Configuración de comportamiento del bot"""

    # ─── RISK MANAGEMENT ──────────────────────────────────────────────
    MAX_RISK_PER_TRADE_PCT = 1.0                 # 1.0% = $500 base. Modo Agresivo de Pruebas.
    STRICT_CONSISTENCY_MODE = True       # Si es True: Anula las variaciones de lotaje por IA o Supervivencia para prop-firms estrictas
    KELLY_FRACTION = 0.5                 # Kelly agresivo: IA puede apalancar más si está muy segura.
    MAX_TRADES_PER_DAY = 10              # Más disparos permitidos por día.
    MAX_OPEN_POSITIONS = 3               # Permite hasta 3 posiciones simultáneas.

    # ─── EMERGENCY THRESHOLDS ─────────────────────────────────────────
    DAILY_DD_WARNING_PCT = 80            # Alerta al 80% del límite diario
    DAILY_DD_EMERGENCY_PCT = 95          # Cierre al 95% del límite diario (Seguridad máxima)
    OVERALL_DD_WARNING_PCT = 80          # Alerta al 80% del límite total ($3,200)
    OVERALL_DD_EMERGENCY_PCT = 95        # Cierre al 95% del límite total ($3,800)

    # ─── STRATEGY ─────────────────────────────────────────────────────
    ORACLE_ENABLED = True                # Habilita o deshabilita la conciencia del CIO Gemini
    SIMULATE_50K_CHALLENGE = False       # Ya es cuenta real de $50K — no necesita simulación
    SIGNAL_MODE_ENABLED = True           # Si es True: Envía señales por Telegram y evita ejecutar órdenes en MT5 (Bypass de restricción EA)
    
    # ─── NEXT-GEN INSTITUTIONAL ARMORY ─────────────────────────────────
    SMC_ENABLED = True                   # Detector de Liquidez (Ahora actúa como 'Asesor Visual', no bloquea trades)
    NEWS_KILLZONES_ENABLED = True        # Radar Alta Frecuencia (Cierre agresivo antes de NFP/CPI)
    PORTFOLIO_REBALANCING = True         # Mapa de Calor Volumétrico (Asignación dinámica entre divisas)
    Q_LEARNING_ENABLED = False           # APAGADO: La IA en pañales frena los trades ("HOLD" por miedo a lo desconocido)
    HEDGING_ENABLED = False              # Cobertura Silenciosa para trades perdedores al 80% del SL
    
    MODE_FILTERS = "STRICT"              # "STRICT" para máxima precisión institucional
    DEFAULT_SYMBOL = "EURUSD"
    WATCHLIST = ["EURUSD", "GBPUSD", "USDJPY"] # Diversificación: Euro, Libra, Yen
    DEFAULT_TIMEFRAME = "M5"             # M5 para entradas más rápidas
    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50
    DEFAULT_SL_PIPS = 20
    DEFAULT_TP_PIPS = 40
    MIN_RR_RATIO = 1.5

    # ─── TRAILING STOP ────────────────────────────────────────────────
    TRAILING_STOP_ENABLED = True
    TRAILING_ACTIVATION_PIPS = 5         # Activar trailing tras +5 pips (Asegurar más rápido)
    TRAILING_STEP_PIPS = 5               # Mover SL cada 5 pips de ganancia

    # ─── ORDERS ───────────────────────────────────────────────────────
    MAGIC_NUMBER = 234000
    DEVIATION = 20
    ORDER_COMMENT_PREFIX = "TX3_Pro"
    MAX_SPREAD_PIPS = 5.0                # TX3 Funding: EURUSD ~2-4, GBPUSD ~4-8, USDJPY ~4-10

    # ─── TIMING ───────────────────────────────────────────────────────
    LOOP_INTERVAL_SECONDS = 2            # Actualización ultra rápida (2s) para Dashboard y MT5
    DAILY_RESET_HOUR_EST = 17
    DAILY_RESET_MINUTE_EST = 0

    # ─── PERSISTENCE ──────────────────────────────────────────────────
    STATE_FILE = "data/bot_state.json"
    JOURNAL_FILE = "data/trade_journal.csv"
    JOURNAL_DETAILED_DIR = "data/journal"

    # ─── NEWS FILTER ──────────────────────────────────────────────────
    NEWS_FILTER_ENABLED = True
    NEWS_AVOID_MINUTES_BEFORE = 30       # No operar 30 min antes de noticia
    NEWS_AVOID_MINUTES_AFTER = 15        # No operar 15 min después


class TelegramConfig:
    """Configuración de Telegram para notificaciones"""

    ENABLED = True
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

    # Qué notificar
    NOTIFY_ON_TRADE = True
    NOTIFY_ON_CLOSE = True
    NOTIFY_ON_DD_WARNING = True
    NOTIFY_ON_DD_EMERGENCY = True
    NOTIFY_ON_PHASE_COMPLETE = True
    NOTIFY_DAILY_SUMMARY = True
    NOTIFY_ON_ERROR = True


class DashboardConfig:
    """Configuración del dashboard web"""

    ENABLED = True
    HOST = "0.0.0.0"
    PORT = 5050
    SECRET_KEY = os.environ.get("DASHBOARD_SECRET", "tx3-pro-bot-secret")
    UPDATE_INTERVAL_MS = 5000            # Actualizar cada 5 segundos
    USERNAME = os.environ.get("DASHBOARD_USER", "dark90")
    PASSWORD = os.environ.get("DASHBOARD_PASS", "971124")
    GUEST_USERNAME = os.environ.get("DASHBOARD_GUEST_USER", "invitado")
    GUEST_PASSWORD = os.environ.get("DASHBOARD_GUEST_PASS", "1234")


class SessionConfig:
    """Configuración de sesiones de trading (EST)"""

    RESTRICT_TO_LONDON_NY = False         # Permitir TODAS las sesiones (LND, NY, ASIA y PACS)
    FRIDAY_FLAT_HOUR = 24                # AJUSTADO: Add-on Weekend Trading activo (No cerrar los viernes)

    LONDON_START_HOUR = 3
    LONDON_START_MINUTE = 0
    LONDON_END_HOUR = 12
    LONDON_END_MINUTE = 0

    NY_START_HOUR = 8
    NY_START_MINUTE = 0
    NY_END_HOUR = 17
    NY_END_MINUTE = 0
    
    TOKYO_START_HOUR = 19
    TOKYO_START_MINUTE = 0
    TOKYO_END_HOUR = 2
    TOKYO_END_MINUTE = 0

    SYDNEY_START_HOUR = 17
    SYDNEY_START_MINUTE = 0
    SYDNEY_END_HOUR = 2
    SYDNEY_END_MINUTE = 0

    OVERLAP_START_HOUR = 8
    OVERLAP_START_MINUTE = 0
    OVERLAP_END_HOUR = 12
    OVERLAP_END_MINUTE = 0

    TRADING_DAYS = [0, 1, 2, 3, 4]       # Lunes a Viernes


class BacktestConfig:
    """Configuración de backtesting"""

    DEFAULT_PERIOD_DAYS = 90             # 3 meses por defecto
    INITIAL_BALANCE = 50_000
    COMMISSION_PER_LOT = 7.0             # $7 por lote round-trip
    SPREAD_PIPS = 1.5                    # Spread simulado
    RESULTS_DIR = "data/backtest_results"
