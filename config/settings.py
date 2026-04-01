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
    BALANCE_INICIAL = 50_000             # 💡 CAMBIA ESTO A 100_000 SI COMPRAS LA DE 100K

    # ─── FASE 1 - Evaluación (FTMO ESTÁNDAR) ──────────────────────────
    FASE1_PROFIT_TARGET_PCT = 10.0
    FASE1_PROFIT_TARGET = BALANCE_INICIAL * (FASE1_PROFIT_TARGET_PCT / 100.0)

    # ─── FASE 2 - Evaluación ──────────────────────────────────────────
    FASE2_PROFIT_TARGET_PCT = 5.0
    FASE2_PROFIT_TARGET = BALANCE_INICIAL * (FASE2_PROFIT_TARGET_PCT / 100.0)

    # ─── DRAWDOWN LIMITS ──────────────────────────────────────────────
    MAX_DAILY_DRAWDOWN_PCT = 5.0
    MAX_DAILY_DRAWDOWN = BALANCE_INICIAL * (MAX_DAILY_DRAWDOWN_PCT / 100.0)

    MAX_OVERALL_DRAWDOWN_PCT = 10.0
    MAX_OVERALL_DRAWDOWN = BALANCE_INICIAL * (MAX_OVERALL_DRAWDOWN_PCT / 100.0)

    # ─── DÍAS MÍNIMOS ─────────────────────────────────────────────────
    MIN_TRADING_DAYS = 4                 # FTMO: 4 Días Mínimos Requeridos
    MIN_PROFIT_PER_DAY = 1.0             # 🔥 FTMO no exige $250. Cualquier día > $1 se marca como rentable/operativo.

    # ─── FUNDED ACCOUNT ───────────────────────────────────────────────
    PROFIT_SPLIT = 90                    # FTMO: Scale Plan permite hasta 90/10
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

    TIMEZONE = "America/Bogota"          # Zona horaria para dashboard, logs y resets
    MARKET_TIMEZONE = "America/New_York"  # 🔥 Zona horaria del mercado (NYSE) — Maneja DST automáticamente
    FTMO_TIMEZONE = "Europe/Prague"      # 🔥 Zona horaria oficial de FTMO (Sincronización Crítica)

    # ─── RISK MANAGEMENT (FTMO COMPLIANCE) ────────────────────────────
    MAX_RISK_PER_TRADE_PCT = 0.4                 # 0.4% = $200 base para cuenta 50K. Modo Conservador para Sobrevivir.
    STRICT_CONSISTENCY_MODE = True       # FTMO exige que no haya "one-sided bets".
    KELLY_FRACTION = 0.0                 # Cero para evitar sobreapalancamiento prohibido por FTMO.
    MAX_TRADES_PER_DAY = 5               # Reducimos los tiros diarios a 5 (Francotirador élite).
    MAX_OPEN_POSITIONS = 2               # Permite hasta solo 2 simultáneas para evitar correlaciones suicidas.
    REVENGE_COOLDOWN_MINUTES = 60        # 1 HORA de bloqueo tras cerrar un trade (Elimina 100% el revenge trading)

    # ─── EMERGENCY THRESHOLDS ─────────────────────────────────────────
    DAILY_DD_WARNING_PCT = 80            # Alerta al 80% del límite diario
    DAILY_DD_EMERGENCY_PCT = 95          # Cierre al 95% del límite diario
    OVERALL_DD_WARNING_PCT = 80          # Alerta al 80% del límite total
    OVERALL_DD_EMERGENCY_PCT = 95        # Cierre al 95% del límite total

    # ─── STRATEGY ─────────────────────────────────────────────────────
    ORACLE_ENABLED = True                # Mantiene la consciencia IA
    SIMULATE_50K_CHALLENGE = False       
    SIGNAL_MODE_ENABLED = False          
    
    # ─── NEXT-GEN INSTITUTIONAL ARMORY ─────────────────────────────────
    SMC_ENABLED = True                   # Detector de Liquidez activo 
    NEWS_KILLZONES_ENABLED = True        # Cierre agresivo ante noticias clave
    PORTFOLIO_REBALANCING = True         
    Q_LEARNING_ENABLED = False           
    HEDGING_ENABLED = False              
    
    MODE_FILTERS = "STRICT"              
    DEFAULT_SYMBOL = "EURUSD"
    WATCHLIST = ["EURUSD", "GBPUSD"]     # 🔥 ELIMINADO AUDUSD/USDJPY: Las pruebas cuantitativas demuestran que destruyen capital.
    DEFAULT_TIMEFRAME = "M5"             
    EMA_FAST_PERIOD = 20
    EMA_SLOW_PERIOD = 50
    DEFAULT_SL_PIPS = 20
    DEFAULT_TP_PIPS = 40
    MIN_RR_RATIO = 1.5

    # ─── TRAILING STOP ────────────────────────────────────────────────
    TRAILING_STOP_ENABLED = True
    TRAILING_ACTIVATION_PIPS = 8         # Asegurar break even un poco más tarde para no ahogar el ruido
    TRAILING_STEP_PIPS = 4               

    # ─── ORDERS ───────────────────────────────────────────────────────
    MAGIC_NUMBER = 234000
    DEVIATION = 20
    ORDER_COMMENT_PREFIX = "Darkobot"
    MAX_SPREAD_PIPS = 4.0                # 🔥 MAX 4 PIPS: Si el broker cobra más, el bot NO opera. Cuida tu capital.

    # ─── TIMING ───────────────────────────────────────────────────────
    LOOP_INTERVAL_SECONDS = 1            # Frecuencia agresiva (1 seg) para FTMO
    DAILY_RESET_HOUR_EST = 17
    DAILY_RESET_MINUTE_EST = 0

    # ─── PERSISTENCE ──────────────────────────────────────────────────
    STATE_FILE = "data/bot_state.json"
    JOURNAL_FILE = "data/trade_journal.csv"
    JOURNAL_DETAILED_DIR = "data/journal"

    # ─── NEWS FILTER ──────────────────────────────────────────────────
    NEWS_FILTER_ENABLED = True
    NEWS_AVOID_MINUTES_BEFORE = 45       # Ser todavía más precavido
    NEWS_AVOID_MINUTES_AFTER = 30        


class TelegramConfig:
    """Configuración de Telegram para notificaciones"""

    ENABLED = True
    # Fallback incorporado en caso de que Windows/PowerShell no comparta las variables del .bat
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8407569871:AAFwcNzt8Mk0U0Bp3MGwT6OAaxHzRhy-2zg")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1176201993")

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
    UPDATE_INTERVAL_MS = 5000            
    USERNAME = os.environ.get("DASHBOARD_USER", "dark90")
    PASSWORD = os.environ.get("DASHBOARD_PASS", "971124")
    GUEST_USERNAME = os.environ.get("DASHBOARD_GUEST_USER", "invitado")
    GUEST_PASSWORD = os.environ.get("DASHBOARD_GUEST_PASS", "1234")


class SessionConfig:
    """Configuración de sesiones de trading (EST)"""

    RESTRICT_TO_LONDON_NY = False        # 🟢 DESACTIVADO: Ahora cada estrategia (Bollinger, ICT, etc.) maneja sus propias horas base (Ej: Asia para ICT)
    FRIDAY_FLAT_HOUR = 15                
    
    # 🔥 MATAMOS TOKIO Y SYDNEY, SOLO LONDRES CRÍTICO Y NY
    LONDON_START_HOUR = 4                # Empezar a las 4 AM EST (Ya pasaron los fakeouts de apertura de las 3 AM)
    LONDON_START_MINUTE = 0
    LONDON_END_HOUR = 12
    LONDON_END_MINUTE = 0

    NY_START_HOUR = 8
    NY_START_MINUTE = 0
    NY_END_HOUR = 16                   # 🛡️ PROTECCIÓN ROLLOVER: Cierre final a las 16:45 PM EST
    NY_END_MINUTE = 45
    
    STRICT_CONSISTENCY_MODE = True       # 🛡️ FTMO LEGAL COMPLIANCE: Mantiene el lote base intocable
    
    TOKYO_START_HOUR = 19
    TOKYO_START_MINUTE = 0
    TOKYO_END_HOUR = 2
    TOKYO_END_MINUTE = 0

    SYDNEY_START_HOUR = 17
    SYDNEY_START_MINUTE = 0
    SYDNEY_END_HOUR = 1
    SYDNEY_END_MINUTE = 0

    # Superposición de volumen máximo
    OVERLAP_START_HOUR = 8
    OVERLAP_START_MINUTE = 0
    OVERLAP_END_HOUR = 12
    OVERLAP_END_MINUTE = 0

    OVERLAP_END_HOUR = 12
    OVERLAP_END_MINUTE = 0

    TRADING_DAYS = [0, 1, 2, 3, 4]       # Lunes a Viernes


class BacktestConfig:
    """Configuración de backtesting"""

    DEFAULT_PERIOD_DAYS = 90             # 3 meses por defecto
    INITIAL_BALANCE = 50_000
    COMMISSION_PER_LOT = 9.0             # $9 por lote (Ajustado por el broker)
    SPREAD_PIPS = 1.5                    # Spread simulado
    RESULTS_DIR = "data/backtest_results"
