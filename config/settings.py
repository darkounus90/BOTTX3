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
    FASE1_PROFIT_TARGET = 5_000          # 10% de 50k
    FASE1_PROFIT_TARGET_PCT = 10.0

    # ─── FASE 2 - Evaluación ──────────────────────────────────────────
    FASE2_PROFIT_TARGET = 2_500          # 5% de 50k
    FASE2_PROFIT_TARGET_PCT = 5.0

    # ─── DRAWDOWN LIMITS ──────────────────────────────────────────────
    MAX_DAILY_DRAWDOWN = 2_500           # 5% de 50k
    MAX_DAILY_DRAWDOWN_PCT = 5.0

    MAX_OVERALL_DRAWDOWN = 5_000         # 10% de 50k (ESTÁTICO, no trailing)
    MAX_OVERALL_DRAWDOWN_PCT = 10.0

    # ─── DÍAS MÍNIMOS ─────────────────────────────────────────────────
    MIN_TRADING_DAYS = 4
    MIN_PROFIT_PER_DAY = 250             # 0.5% mínimo por día contable

    # ─── FUNDED ACCOUNT ───────────────────────────────────────────────
    PROFIT_SPLIT = 80                    # 80% (90% con add-on)
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
    MAX_RISK_PER_TRADE_PCT = 0.5
    MAX_TRADES_PER_DAY = 5
    MAX_OPEN_POSITIONS = 1               # Solo 1 posición a la vez (conservador)

    # ─── EMERGENCY THRESHOLDS ─────────────────────────────────────────
    DAILY_DD_WARNING_PCT = 70            # Alerta al 70% ($1,750)
    DAILY_DD_EMERGENCY_PCT = 85          # Cierre al 85% ($2,125)
    OVERALL_DD_WARNING_PCT = 70          # Alerta al 70% ($3,500)
    OVERALL_DD_EMERGENCY_PCT = 85        # Cierre al 85% ($4,250)

    # ─── STRATEGY ─────────────────────────────────────────────────────
    DEFAULT_SYMBOL = "EURUSD"
    WATCHLIST = ["EURUSD", "GBPUSD", "USDJPY"] # Diversificación: Euro, Libra, Yen
    DEFAULT_TIMEFRAME = "M15"
    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50
    DEFAULT_SL_PIPS = 20
    DEFAULT_TP_PIPS = 40
    MIN_RR_RATIO = 1.5

    # ─── TRAILING STOP ────────────────────────────────────────────────
    TRAILING_STOP_ENABLED = True
    TRAILING_ACTIVATION_PIPS = 15        # Activar trailing tras +15 pips
    TRAILING_STEP_PIPS = 5               # Mover SL cada 5 pips de ganancia

    # ─── ORDERS ───────────────────────────────────────────────────────
    MAGIC_NUMBER = 234000
    DEVIATION = 20
    ORDER_COMMENT_PREFIX = "TX3_Pro"

    # ─── TIMING ───────────────────────────────────────────────────────
    LOOP_INTERVAL_SECONDS = 30
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


class SessionConfig:
    """Configuración de sesiones de trading (EST)"""

    LONDON_START_HOUR = 3
    LONDON_START_MINUTE = 0
    LONDON_END_HOUR = 12
    LONDON_END_MINUTE = 0

    NY_START_HOUR = 8
    NY_START_MINUTE = 0
    NY_END_HOUR = 17
    NY_END_MINUTE = 0

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
