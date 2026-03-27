"""
🤖 TX3 Pro Bot $50K - Main Entry Point (Professional Edition)
===============================================================
Bot de trading automatizado para el 2 Phase Pro Challenge
de TX3 Funding ($50,000).

Incluye:
- 📱 Telegram Notifications
- 🌐 Web Dashboard (Real-time)
- 💾 State Persistence
- 📰 News Filter
- 🔄 Trailing Stop
- 🛡️ Advanced Risk Management

Uso:
    python main.py --phase 1           # Fase 1 (10% target)
    python main.py --phase 2           # Fase 2 (5% target)
    python main.py --phase 1 --dry-run # Solo señales, sin operar
"""

import argparse
import signal
import sys
import threading
import time as sleep_module
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from config.settings import ChallengeConfig, BotConfig, DashboardConfig, TelegramConfig
from core.risk_manager import RiskManager
from core.position_manager import PositionManager
from core.phase_tracker import PhaseTracker
from core.session_filter import SessionFilter
from core.news_filter import NewsFilter
from core.trailing_stop import TrailingStopManager
from core.llm_oracle import GeminiOracle
from strategy.zscore_reversion import ZScoreReversionStrategy
from strategy.ttm_squeeze import TTMSqueezeStrategy
from strategy.liquidity_sweep import LiquiditySweepStrategy
from strategy.institutional_flow import InstitutionalFlowStrategy
from strategy.london_open_purge import LondonOpenPurgeStrategy
from utils.logger import BotLogger
from utils.mt5_connector import MT5Connector
from utils.telegram_notifier import TelegramNotifier
from utils.trade_journal import TradeJournal
from utils.state_manager import StateManager
from dashboard.app import run_dashboard, update_dashboard_data, add_dashboard_log
from utils.telegram_commands import TelegramCommandHandler
from core.smc_scanner import SMCScanner
from core.portfolio_manager import PortfolioManager
from core.correlation_manager import CorrelationManager
from strategy.q_learning_agent import QLearningAgent


class TX3ProBot:
    """
    Bot principal profesional.
    Integra todos los módulos de gestión, trading y monitoreo.
    """

    def __init__(self, phase: int, dry_run: bool = False):
        self.phase = phase
        self.dry_run = dry_run
        self.running = False
        self.daily_reset_done = False
        self.is_paused = False
        self._last_loop_timestamp = sleep_module.time()
        self._watchdog_notified = False
        self._last_signal_found_timestamp = sleep_module.time() # Seguir rastro de última señal detectada
        self._in_hibernation = False # Modo ahorro de energía/logs
        self._notified_disconnect = False
        self._last_scan_log = {}
        self._last_heartbeat_log = {}
        self._last_cd_log = {}
        self.last_mutation_day = 0
        self.last_training_day = 0

        # ─── Inicializar componentes ─────────────────────────────────
        self.logger = BotLogger(name="TX3Bot")
        self.connector = MT5Connector(logger=self.logger)
        
        # Notificaciones y Persistencia
        self.telegram = TelegramNotifier(logger=self.logger)
        self.telegram_commands = TelegramCommandHandler(logger=self.logger, bot_reference=self)
        self.state_manager = StateManager(logger=self.logger)
        self.journal = TradeJournal(logger=self.logger, phase=phase)

        # Core Logic
        self.risk_manager = RiskManager(logger=self.logger)
        self.position_manager = PositionManager(
            logger=self.logger, 
            phase=self.phase, 
            risk_manager=self.risk_manager
        )
        self.phase_tracker = PhaseTracker(logger=self.logger, phase=phase)
        self.session_filter = SessionFilter(logger=self.logger)
        
        # Pro Features
        self.news_filter = NewsFilter(logger=self.logger)
        self.oracle = GeminiOracle(logger=self.logger) # Oráculo primero
        self.trailing_stop = TrailingStopManager(logger=self.logger, oracle=self.oracle) # Se inyecta al Trailing
        
        # Next-Gen Institutional features
        self.smc_scanner = SMCScanner(logger=self.logger)
        self.portfolio_manager = PortfolioManager(logger=self.logger)
        self.correlation_manager = CorrelationManager(logger=self.logger)
        self.q_agent = QLearningAgent(logger=self.logger)
        
        # Estrategias (Backtest-Optimized: Solo las que demostraron rentabilidad)
        # ⚠️ Las 4 estrategias de Breakout (NY, London, Tokyo, Sydney) fueron 
        # DESACTIVADAS por el Backtester Cuantitativo (2026-03-18).
        # Todas mostraron PF < 1.0 y Win Rate < 40% en ambos pares durante 60 días.
        self.strategies = {}
        for symbol in BotConfig.WATCHLIST:
            if symbol == "GBPUSD":
                # 🏆 GBPUSD: ELITE TEAM (The Big Four)
                self.strategies[symbol] = [
                    ZScoreReversionStrategy(logger=self.logger, symbol=symbol),
                    LiquiditySweepStrategy(logger=self.logger, symbol=symbol),
                    TTMSqueezeStrategy(logger=self.logger, symbol=symbol),
                    InstitutionalFlowStrategy(symbol=symbol, logger=self.logger)
                ]
                self.logger.info(f"✅ ESTRATEGIAS ELITE CARGADAS: [Z-Score + ILS + Squeeze + IFS SMC] → {symbol}")
            elif symbol == "EURUSD":
                # 🥇 EURUSD: ELITE SETUP (Momentum Puro)
                self.strategies[symbol] = [
                    TTMSqueezeStrategy(logger=self.logger, symbol=symbol)
                ]
                self.logger.info(f"✅ Estrategias RENTABLES cargadas: [TTM Squeeze] → {symbol}")
            else:
                self.strategies[symbol] = []

        # Cargar estado previo si existe
        self._restore_state()

        # Registrar señales de cierre
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _restore_state(self):
        """Intenta restaurar el estado del bot desde disco"""
        state = self.state_manager.load_state()
        if state:
            try:
                # Restaurar valores críticos
                self.phase_tracker.profitable_days = state.get("profitable_days", 0)
                self.phase_tracker.daily_profits = state.get("daily_profits", [])
                self.phase_tracker.total_trading_days = state.get("total_trading_days", 0)
                
                # 🛡️ PROTECCIÓN DE CAPITAL: 
                # Solo restauramos el balance si es MAYOR al del Challenge (indica profit anterior).
                # Si es menor, mantenemos los 50,000 del Challenge para calcular el Drawdown correctamente.
                saved_balance = state.get("balance_inicial", 0)
                if saved_balance > ChallengeConfig.BALANCE_INICIAL:
                    self.risk_manager.balance_inicial = saved_balance
                    self.phase_tracker.balance_inicial = saved_balance
                else:
                    self.logger.info(f"🛡️ Manteniendo base de ${ChallengeConfig.BALANCE_INICIAL:,.2f} para cálculo de Drawdown real.")
                
                # Restaurar equity inicio día (solo si es el mismo día)
                saved_equity = state.get("equity_inicio_dia", 0)
                if saved_equity > 0:
                     self.risk_manager.equity_inicio_dia = saved_equity
                
                self.logger.success("Estado restaurado correctamente")
            except Exception as e:
                self.logger.error(f"Error restaurando estado parcial: {e}")

    def _save_state(self):
        """Guarda el estado actual a disco"""
        state = self.state_manager.build_state(
            phase=self.phase,
            balance_inicial=self.risk_manager.balance_inicial,
            equity_inicio_dia=self.risk_manager.equity_inicio_dia,
            profitable_days=self.phase_tracker.profitable_days,
            daily_profits=self.phase_tracker.daily_profits,
            total_trading_days=self.phase_tracker.total_trading_days,
            trades_today=self.position_manager.trades_today,
            highest_balance=0, # Placeholder
            is_daily_warning=self.risk_manager.is_daily_warning,
            is_overall_warning=self.risk_manager.is_overall_warning,
        )
        self.state_manager.save_state(state)

    def _handle_shutdown(self, signum, frame):
        """Maneja el cierre limpio"""
        self.logger.separator("═")
        self.logger.warning("🛑 Señal de cierre recibida")
        self.running = False

    def _print_startup_banner(self):
        """Muestra el banner de inicio"""
        self.logger.banner("🤖 TX3 PRO BOT $50K - PROFESSIONAL")
        self.logger.info(f"  Fase:          {self.phase}")
        self.logger.info(f"  Modo:          {'🔍 DRY RUN' if self.dry_run else '🟢 LIVE'}")
        self.logger.info(f"  Estado:        {'⏸️ PAUSADO' if self.is_paused else '▶️ ACTIVO'}")
        self.logger.info(f"  Dashboard:     http://{DashboardConfig.HOST}:{DashboardConfig.PORT}")
        self.logger.info(f"  News Filter:   {'✅ Enabled' if self.news_filter.enabled else '❌ Disabled'}")
        self.logger.info(f"  Trailing Stop: {'✅ Enabled' if self.trailing_stop.enabled else '❌ Disabled'}")
        self.logger.separator("═")

    def _update_dashboard(self):
        """Envía datos actualizados al dashboard web"""
        if not DashboardConfig.ENABLED:
            return

        account = self.connector.get_account_info()
        positions = self.position_manager.get_open_positions()
        
        daily_dd = self.risk_manager.check_daily_drawdown()
        overall_dd = self.risk_manager.check_overall_drawdown()
        
        # Determinar MODE mental
        bot_mode = "off"
        if self.running and not self.is_paused:
            if daily_dd["level"] in ("WARNING", "EMERGENCY") or overall_dd["level"] in ("WARNING", "EMERGENCY"):
                bot_mode = "defense"
            else:
                bot_mode = "normal"
        elif self.is_paused:
            bot_mode = "paused"

        # Formatear posiciones para JSON
        pos_list = []
        live_exposures = {}
        risk_pct_session = 0.0
        balance = account["balance"] if account else 0
        
        for p in positions:
            # Calcular risk_pct_trade (pips a SL * valor / balance)
            risk_pct_trade = 0.0
            if p.sl > 0 and balance > 0:
                profit = mt5.order_calc_profit(p.type, p.symbol, p.volume, p.price_open, p.sl)
                if profit is not None and profit < 0:
                    risk_pct_trade = (abs(profit) / balance) * 100.0
            
            risk_pct_session += risk_pct_trade
            if p.symbol not in live_exposures:
                 live_exposures[p.symbol] = 0.0
            live_exposures[p.symbol] += risk_pct_trade
            
            # Extraer strategy_id de comment (por ej: "Breakout_P1") -> "Breakout"
            strat_id = p.comment.split("_P")[0] if p.comment else "Automated"
            
            # Determinar "Intent" basado en el comentario (puede ampliarse)
            intent = "Apertura"
            if p.comment:
                c_low = p.comment.lower()
                if "sca" in c_low or "_s" in c_low:
                    intent = "Escala"
                elif "hedg" in c_low or "_h" in c_low:
                    intent = "Cobertura"

            pos_list.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "strategy_id": strat_id,
                "trade_intent": intent,
                "risk_pct_trade": round(risk_pct_trade, 3),
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "profit": p.profit,
                "sl": p.sl,
                "tp": p.tp
            })

        # Calcular Win Rate rápido basado en el historial de trades cerrados hoy + abiertos
        win_rate = 0.0
        # Simplificación de win_rate visual (podrías guardarlo en un state si quisieras, aquí lo dejamos en 0.0 o aproximado si tuvieras history real)

        # Calcular trades de hoy desde el historial (usa la timezone del bot)
        today_str = datetime.now(ZoneInfo(BotConfig.TIMEZONE)).strftime("%Y-%m-%d")
        recent_trades = self.journal.get_recent_trades(limit=50)
        trades_hoy = len([t for t in recent_trades if t.get('timestamp', '').startswith(today_str)])
        
        # O usar el mayor entre el journal y el de memoria
        total_trades_display = max(trades_hoy, self.position_manager.trades_today)

        # Estado Operativo Real (basado en horarios reales de estrategias activas: 03:00-17:00 EST)
        hour_est = datetime.now(ZoneInfo(BotConfig.TIMEZONE)).hour
        is_in_active_window = 3 <= hour_est < 17
        bot_status = "🟢 OPERACIONAL" if is_in_active_window else "💤 ZONA MUERTA"
        
        data = {
            "bot_status": bot_status,
            "status": "PAUSED" if self.is_paused else ("RUNNING" if self.running else "STOPPED"),
            "mode": bot_mode,
            "sim_mode": "DEMO" if self.dry_run else "LIVE",
            "risk_pct_session": round(risk_pct_session, 3),
            "kelly_fraction": BotConfig.KELLY_FRACTION,
            "phase": self.phase,
            "balance": account["balance"] if account else 0,
            "equity": account["equity"] if account else 0,
            "daily_profit": self.phase_tracker.current_day_profit,
            "daily_dd": daily_dd["loss"],
            "daily_dd_limit": daily_dd.get("limit", 2500),
            "overall_dd": overall_dd["loss"],
            "overall_dd_limit": overall_dd.get("limit", 5000),
            "oracle_reasoning_log": self.oracle.get_reasoning_history() if hasattr(self.oracle, 'get_reasoning_history') else [],
            "profit_target": self.phase_tracker.profit_target,
            "profitable_days": self.phase_tracker.profitable_days,
            "min_days": self.phase_tracker.min_trading_days,
            "consistency_met": self.phase_tracker.check_consistency_rule(),
            "total_trades": total_trades_display,
            "win_rate": 0.0, # Placeholder, actual logging occurs in journaling if implemented
            "sys_mt5": self.connector.is_connected(),
            "sys_oracle": self.oracle.system_ready if hasattr(self, 'oracle') else False,
            "sys_news": self.news_filter.enabled if hasattr(self, 'news_filter') else False,
            "simulate_50k": getattr(BotConfig, "SIMULATE_50K_CHALLENGE", False),
            "session_info": self.session_filter.get_session_info() if hasattr(self, 'session_filter') else {},
            "upcoming_news": [
                {
                    "title": e.get("title", ""),
                    "currency": e.get("currency", ""),
                    "time": e.get("time").strftime("%H:%M") if e.get("time") else ""
                }
                for e in (self.news_filter.get_upcoming_events(24) if hasattr(self, 'news_filter') else [])
            ][:3],
            "open_positions": pos_list,
            "live_exposures": live_exposures,
            "recent_trades": self.journal.get_recent_trades(limit=15),
            "last_oracle_narration": self.oracle.last_narration if hasattr(self, 'oracle') else "No disponible",
            "correlation_exposure": self.correlation_manager.get_exposure_report() if hasattr(self, 'correlation_manager') else {},
            "latency_ms": getattr(mt5.terminal_info(), "ping_last", 0) / 1000.0 if mt5.terminal_info() else 0,
            "last_update": datetime.now(ZoneInfo(BotConfig.TIMEZONE)).strftime("%H:%M:%S")
        }
        
        # ─── Spreads en Tiempo Real ─────────────────────────
        spreads_data = {}
        for sym in BotConfig.WATCHLIST:
            try:
                si = mt5.symbol_info(sym)
                if si:
                    # Fix matemático visual (Dashboard)
                    sp = si.spread / 10.0
                    spreads_data[sym] = {
                        "spread": round(sp, 1),
                        "ok": sp <= BotConfig.MAX_SPREAD_PIPS
                    }
            except Exception:
                pass
        data["spreads"] = spreads_data
        data["max_spread"] = BotConfig.MAX_SPREAD_PIPS
        
        # ─── Log de Resumen al Dashboard (cada 60s) ────────
        now_dt = datetime.now()
        if self._last_dash_summary is None or (now_dt - self._last_dash_summary).total_seconds() >= 60:
            self._last_dash_summary = now_dt
            session_info = self.session_filter.get_session_info() if hasattr(self, 'session_filter') else {}
            session_name = session_info.get('session', 'Desconocida')
            open_pos = self.position_manager.get_open_positions_count()
            
            spread_parts = []
            for sym, sd in spreads_data.items():
                icon = "✅" if sd["ok"] else "❌"
                spread_parts.append(f"{sym}: {sd['spread']}p {icon}")
            spread_str = " | ".join(spread_parts)
            
            add_dashboard_log(
                f"📡 Sesión: {session_name} | Spreads: {spread_str} | "
                f"Posiciones: {open_pos}/{BotConfig.MAX_OPEN_POSITIONS} | "
                f"Trades hoy: {total_trades_display}"
            )
        
        update_dashboard_data(data)

    def _check_daily_reset(self):
        """Verifica reset diario (5 PM EST)"""
        if self.session_filter.is_daily_reset_time():
            if not self.daily_reset_done:
                self.logger.banner("📅 RESET DIARIO - 5 PM EST")
                
                # Lógica de fin de día
                self.phase_tracker.end_of_day()
                self.risk_manager.reset_daily()
                self.position_manager.reset_daily()

                # Enviar resumen
                self.telegram.notify_daily_summary(
                    phase=self.phase,
                    day_profit=self.phase_tracker.daily_profits[-1] if self.phase_tracker.daily_profits else 0,
                    total_profit=self.phase_tracker.get_current_profit(),
                    profit_target=self.phase_tracker.profit_target,
                    profitable_days=self.phase_tracker.profitable_days,
                    min_days=self.phase_tracker.min_trading_days,
                    daily_dd=0,
                    overall_dd=self.risk_manager.check_overall_drawdown()["loss"],
                    trades_today=0,
                    win_rate=0 
                )
                
                self.daily_reset_done = True
                self._save_state()
        else:
            self.daily_reset_done = False

    def _run_genetic_optimizer(self):
        """Ejecuta la optimización genética en segundo plano"""
        try:
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(__file__), "scripts", "genetic_optimizer.py")
            subprocess.run(["python", script_path], check=True)
            self.logger.success("🧬 Mutación genética completada. Parámetros actualizados.")
        except Exception as e:
            self.logger.error(f"Error en Mutación Genética: {e}")

    def _run_ml_trainer(self):
        """Ejecuta el reentrenamiento del cerebro IA en segundo plano"""
        try:
            import subprocess
            import os
            script_path = os.path.join(os.path.dirname(__file__), "scripts", "train_ml_model.py")
            subprocess.run(["python", script_path], check=True)
            # Reinstanciar la estrategia con el nuevo cerebro
            for symbol in BotConfig.WATCHLIST:
                if type(self.strategies.get(symbol)).__name__ == "MLRandomForestStrategy":
                    from strategy.ml_random_forest import MLRandomForestStrategy
                    self.strategies[symbol] = MLRandomForestStrategy(logger=self.logger, symbol=symbol)
            self.logger.success("🧠 Cerebro IA reentrenado y recargado en memoria.")
        except Exception as e:
            self.logger.error(f"Error entrenando IA: {e}")

    def _run_ai_health_monitor_loop(self):
        """Ciclo de vida del Dr. Quant: Revisa la telemetría periódicamente y alerta preventivamente."""
        import time
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        
        _TZ = ZoneInfo(BotConfig.TIMEZONE)
        
        # Esperar 5 minutos al iniciar antes de hacer el primer chequeo
        time.sleep(300)
        
        while self.running:
            try:
                now_et = datetime.now(_TZ)
                weekday = now_et.weekday()  # 0=Lun, 4=Vie, 5=Sáb, 6=Dom
                
                # ─── SKIP FIN DE SEMANA ─────────────────────────
                # No alertar: Viernes después de 5 PM, Sábado, Domingo,
                # ni Lunes antes de 10 AM (el mercado aún no tiene actividad real)
                is_market_closed = False
                if weekday == 4 and now_et.hour >= 17:  # Viernes >= 5 PM
                    is_market_closed = True
                elif weekday in (5, 6):  # Sábado o Domingo
                    is_market_closed = True
                elif weekday == 0 and now_et.hour < 10:  # Lunes antes de 10 AM
                    is_market_closed = True
                
                if is_market_closed:
                    # Dormir y saltar — no tiene sentido alertar con mercado cerrado
                    for _ in range(21600):
                        if not self.running: break
                        time.sleep(1)
                    continue
                
                # Recopilar métricas
                uptime_str = "Desconocido"
                if hasattr(self.telegram_commands, "_start_time"):
                    delta = datetime.now() - self.telegram_commands._start_time
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    uptime_str = f"{hours}h {minutes}m"
                    
                hours_since_last = "Sin trades del bot"
                hours_diff = 0
                bot_has_traded = False
                try:
                    import MetaTrader5 as mt5
                    now = datetime.now()
                    back = now - timedelta(days=30)
                    deals = mt5.history_deals_get(back, now)
                    if deals and len(deals) > 0:
                        # Solo contar trades del BOT (filtrar por MAGIC_NUMBER)
                        bot_deals = [d for d in deals if d.magic == BotConfig.MAGIC_NUMBER]
                        if bot_deals:
                            bot_has_traded = True
                            last_deal_time = datetime.fromtimestamp(bot_deals[-1].time)
                            hours_diff = (now - last_deal_time).total_seconds() / 3600
                            hours_since_last = f"{hours_diff:.1f}h"
                except Exception:
                    pass
                    
                daily_dd = self.risk_manager.check_daily_drawdown()["loss"]
                overall_dd = self.risk_manager.check_overall_drawdown()["loss"]
                
                # Criterios de Emergencia
                is_emergency = False
                trigger_reason = ""
                
                # Inactividad: Solo alertar si el BOT ha operado antes
                # (no alertar si el bot nunca ha hecho un trade — es cuenta nueva)
                if bot_has_traded and hours_diff > 48:
                    # Descontar horas de fin de semana (~48h por cada weekend)
                    weekends_in_period = hours_diff // 168
                    weekend_hours = weekends_in_period * 48
                    if now_et.weekday() <= 1:
                        weekend_hours += 48
                    trading_hours = hours_diff - weekend_hours
                    
                    if trading_hours > 48:
                        is_emergency = True
                        trigger_reason = f"⚠️ Inactividad Prolongada ({trading_hours:.0f}h hábiles sin trades del bot)"
                elif overall_dd > (ChallengeConfig.MAX_OVERALL_DRAWDOWN * 0.5):
                    is_emergency = True
                    trigger_reason = "📉 Drawdown Crítico Acumulado"
                    
                if is_emergency:
                    self.logger.warning(f"🩺 Dr. Quant detectó una anomalía ({trigger_reason}). Consultando Oráculo...")
                    metrics = {
                        "uptime": uptime_str,
                        "hours_since_last_trade": hours_since_last,
                        "balance": self.risk_manager.balance_inicial,
                        "daily_dd": daily_dd,
                        "daily_dd_pct": (daily_dd / self.risk_manager.balance_inicial) * 100 if self.risk_manager.balance_inicial > 0 else 0,
                        "overall_dd": overall_dd,
                        "overall_dd_pct": (overall_dd / self.risk_manager.balance_inicial) * 100 if self.risk_manager.balance_inicial > 0 else 0,
                        "mt5_connected": self.connector.is_connected(),
                        "recent_errors": "Revisar logs urgentes."
                    }
                    diagnosis = self.oracle.evaluate_system_health(metrics)
                    self.telegram_commands._send_message(self.telegram_commands.chat_id, f"🚨 *ALERTA PROACTIVA DR. QUANT* 🚨\n_Motivo: {trigger_reason}_\n\n{diagnosis}")
            
            except Exception as e:
                self.logger.error(f"Error en Hilo del Monitor de Salud: {e}")
                
            # Dormir 6 horas (21600 segundos)
            for _ in range(21600):
                if not self.running: break
                time.sleep(1)

    def run_preflight_checks(self) -> bool:
        """🩺 Ejecuta diagnósticos técnicos antes de empezar a operar"""
        self.logger.banner("🧪 INICIANDO AUTO-PRUEBA DE SISTEMAS")
        checklist = {
            "Conexión MT5": False,
            "Símbolos Watchlist": False,
            "Chief Oracle (IA)": False,
            "Gestor de Riesgo": False,
            "Notificaciones Telegram": False
        }

        try:
            # 1. Verificar MT5 y AutoTrading
            if self.connector.is_connected():
                acc = mt5.account_info()
                if acc:
                    self.logger.success(f"🔹 MT5: Conectado a Cuenta {acc.login} ({acc.company})")
                    checklist["Conexión MT5"] = True
                    
                    if not acc.trade_allowed:
                        self.logger.error("❌ EL BROKER BLOQUEÓ EL ALGO TRADING (code 10026). Tu cuenta no tiene permisos del servidor para usar bots.")
                        self.telegram.notify_error("❌ Error de Broker: El servidor tiene bloqueado el Auto Trading en tu cuenta. Escribe al soporte técnico de tu Prop Firm para que te lo activen.")
                
                ti = mt5.terminal_info()
                if ti and not ti.trade_allowed:
                    self.logger.warning("⚠️ MT5 ALGO TRADING APAGADO: El botón 'Algo Trading' (arriba en MT5) está en rojo. El bot no podrá colocar órdenes.")
                    self.telegram.notify_error("⚠️ Atención: El botón 'Algo Trading' en MT5 está apagado. Actívalo para no perder señales.")
            
            # 2. Verificar Símbolos
            missing_symbols = []
            for sym in BotConfig.WATCHLIST:
                if not self.connector.ensure_symbol_available(sym):
                    missing_symbols.append(sym)
            if not missing_symbols:
                self.logger.success(f"🔹 Watchlist: Todos los símbolos ({len(BotConfig.WATCHLIST)}) disponibles.")
                checklist["Símbolos Watchlist"] = True
            else:
                self.logger.error(f"❌ Error Símbolos: No disponibles -> {missing_symbols}")

            # 3. Probar Oráculo (IA)
            if self.oracle.enabled:
                test_q = self.oracle.ask_oracle("Ping rápido de diagnóstico. Di 'Sistemas OK' y un emoji.")
                if "Sistemas OK" in test_q or "Oráculo" in test_q or "OK" in test_q:
                    self.logger.success(f"🔹 Oráculo IA: Respuesta recibida -> {test_q}")
                    checklist["Chief Oracle (IA)"] = True
                else:
                    self.logger.warning(f"⚠️ Oráculo IA: Respondio de forma inesperada pero conectó.")
                    checklist["Chief Oracle (IA)"] = True
            else:
                self.logger.warning("⚠️ Oráculo IA: Está desactivado.")
                checklist["Chief Oracle (IA)"] = True

            # 4. Verificar Riesgo
            current_dd = self.risk_manager.check_overall_drawdown()
            if current_dd["level"] not in ("EMERGENCY", "VIOLATED"):
                self.logger.success(f"🔹 Riesgo: Drawdown actual estable ({current_dd['loss']:.2f})")
                checklist["Gestor de Riesgo"] = True
            else:
                self.logger.critical("🚨 Riesgo: La cuenta ya está en nivel de DRAWDOWN CRÍTICO.")

            # 5. Probar Telegram
            if TelegramConfig.ENABLED:
                # No enviamos mensaje pesado, solo verificamos que los parámetros existan
                if TelegramConfig.BOT_TOKEN and TelegramConfig.CHAT_ID:
                    self.logger.success("🔹 Telegram: Configuración de envío detectada.")
                    checklist["Notificaciones Telegram"] = True
                else:
                    self.logger.error("❌ Telegram: Faltan credenciales (Token/ChatId).")

        except Exception as e:
            self.logger.error(f"Fallo durante la auto-prueba: {e}")

        # Recuento Final
        success = all(checklist.values())
        if success:
            self.logger.success("✨ AUTO-PRUEBA COMPLETADA: Todos los sistemas están operativos.")
        else:
            failed = [k for k, v in checklist.items() if not v]
            self.logger.error(f"❌ FALLO TÉCNICO en: {failed}")
        
        return success

    def run(self):
        """Loop principal"""
        # 1. Iniciar Dashboard en thread
        if DashboardConfig.ENABLED:
            dash_thread = threading.Thread(
                target=run_dashboard, 
                args=(self.logger,), 
                daemon=True
            )
            dash_thread.start()

        self.telegram_commands.start()

        # 1.5 Iniciar Dr. Quant Health Monitor
        if hasattr(self, "oracle") and self.oracle.enabled:
            health_thread = threading.Thread(
                target=self._run_ai_health_monitor_loop,
                daemon=True
            )
            health_thread.start()

        # 2. Conexión y Setup
        if not self.connector.connect():
            self.logger.error("Fallo al conectar a MT5")
            return
            
        # Check if any symbol from WATCHLIST is available
        # This check was originally for self.strategy.symbol, now it needs to be adapted
        # For simplicity, we'll just ensure connection and let individual symbol checks handle availability.
        # if not self.connector.ensure_symbol_available(self.strategy.symbol):
        #     self.logger.error(f"Símbolo {self.strategy.symbol} no disponible")
        #     return

        # ─── Capturar balance real de MT5 ──────────────────────────
        account_info = mt5.account_info()
        if account_info:
            real_balance = account_info.balance
            # 🛡️ PROTECCIÓN DE CAPITAL:
            # NO SOBREESCRIBIR el balance inicial con el balance actual si estamos en drawdown.
            # _restore_state() ya lo inicializó al valor de ChallengeConfig.BALANCE_INICIAL (ej. 50k) 
            # o al valor escalado si superamos los 50k. 
            self.logger.info(f"⚖️ Sincronizando: Balance inicial anclado en ${self.risk_manager.balance_inicial:,.2f} | Balance real MT5: ${real_balance:,.2f}")
            
            # Asegurar que los módulos compartan el mismo anclaje de seguridad
            self.phase_tracker.balance_inicial = self.risk_manager.balance_inicial
            
            # Setup equity inicio día si es necesario
            if self.risk_manager.equity_inicio_dia == ChallengeConfig.BALANCE_INICIAL:
                self.risk_manager.equity_inicio_dia = max(real_balance, account_info.equity)
        
        self._print_startup_banner()
        
        # 🧪 PRE-FLIGHT DIAGNOSTICS (Auto-Prueba de Sistemas)
        if not self.run_preflight_checks():
            self.logger.critical("🛑 AUTO-PRUEBA FALLIDA: El bot no puede iniciar con errores críticos.")
            self.telegram.notify_error("🚨 FALLO DE INICIO: Auto-prueba técnica fallida. Revisa los logs.")
            return

        # 🩺 SINCRONIZACIÓN INICIAL DE HISTORIAL (Consistencia Dashboard y Alertas)
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            # Ventana generosa (48h atrás, 24h adelante) para cubrir brokers con GMT extremo
            sync_start = now - timedelta(hours=48)
            sync_end = now + timedelta(hours=24)
            deals_sync = mt5.history_deals_get(sync_start, sync_end)
            
            if deals_sync:
                new_trades = self.journal.sync_mt5_history(deals_sync)
                # 🔔 NOTIFICACIÓN RETROACTIVA: Si el bot estaba apagado y hubo cierres, avisa ahora.
                if new_trades:
                    self.logger.info(f"🔔 Detectados {len(new_trades)} cierres externos. Notificando...")
                    for trade in new_trades:
                        self.telegram.notify_trade_closed(
                            symbol=trade.get("symbol", "N/A"),
                            order_type=trade.get("type", "N/A"),
                            volume=trade.get("volume", 0.0),
                            profit=trade.get("profit", 0.0),
                            pips=0.0,
                            duration="MT5 Startup Sync"
                        )
        except Exception as e:
            self.logger.warning(f"No se pudo sincronizar historial inicial: {e}")

        # 📅 RECALCULAR DÍAS RENTABLES del historial real de MT5
        try:
            self.phase_tracker.recalculate_profitable_days_from_mt5()
        except Exception as e:
            self.logger.warning(f"No se pudieron recalcular días rentables: {e}")

        self.telegram.notify_bot_started(
            phase=self.phase,
            dry_run=self.dry_run,
            balance=real_balance if account_info else 0,
            watchlist=BotConfig.WATCHLIST,
        )

        self.running = True
        self._notified_disconnect = False
        reconnect_attempts = 0
        
        # Estado Interno
        self._last_dash_summary = None
        
        # Suscribir al sistema de Journaling ─────────────────────────
        
        # Iniciar Watchdog Thread (Independiente del loop principal)
        watchdog_thread = threading.Thread(target=self._run_watchdog_loop, daemon=True)
        watchdog_thread.start()
        
        last_heartbeat = datetime.now()
        
        while self.running:
            try:
                # ─── Heartbeat (Evitar silencios largos) ─────────
                now = datetime.now()
                self._last_loop_timestamp = sleep_module.time() # Actualizar Watchdog
                
                if (now - last_heartbeat).total_seconds() >= 900: # Cada 15 min
                    self.logger.info("💓 Heartbeat: Loop principal activo y monitoreando mercado...")
                    last_heartbeat = now

                # ─── A. Monitoreo y Mantenimiento ──────────────────
                if not self.connector.is_connected():
                    if not self._notified_disconnect:
                        self.telegram.notify_error("🔌 ALERTA: Conexión con MetaTrader 5 perdida. Intentando reconectar automáticamente...")
                        self._notified_disconnect = True
                        
                    self.logger.warning("Intentando reconexión a MT5...")
                    reconnect_attempts += 1
                    
                    if not self.connector.connect():
                        sleep_module.sleep(10)
                        continue
                    else:
                        self.telegram.notify_reconnection(reconnect_attempts)
                        self._notified_disconnect = False
                        reconnect_attempts = 0
                
                # Sincronizar trades cerrados por el broker (SL/TP/Trailing/Manual)
                try:
                    # Usamos una ventana de 24 horas adelante para cubrir desfasajes GMT extremos entre servidor y broker
                    sync_start_time = datetime.now() - timedelta(hours=48)
                    sync_end_time = datetime.now() + timedelta(hours=24)
                    deals_sync = mt5.history_deals_get(sync_start_time, sync_end_time)
                    
                    if deals_sync is not None:
                        new_trades = self.journal.sync_mt5_history(deals_sync)
                        if new_trades:
                            for trade in new_trades:
                                self.telegram.notify_trade_closed(
                                    symbol=trade.get("symbol", "N/A"),
                                    order_type=trade.get("type", "N/A"),
                                    volume=trade.get("volume", 0.0),
                                    profit=trade.get("profit", 0.0),
                                    pips=trade.get("profit_pips", 0.0), # Corregido de 'pips'
                                    duration="MT5 Sync"
                                )
                    else:
                        err = mt5.last_error()
                        if err[0] != 1:
                            self.logger.debug(f"MT5 history_deals_get vacío o error: {err}")
                except Exception as e:
                    self.logger.error(f"Error en loop de sincronización de historial: {e}")

                self.phase_tracker.update_daily_profit()
                self._check_daily_reset()
                self._update_dashboard()
                
                # ─── ZONA DE PÁNICO DE NOTICIAS (News Killzone) ─────
                if self.news_filter.enabled:
                    try:
                        upcoming_news = self.news_filter.get_upcoming_events(hours_ahead=1)
                        if upcoming_news:
                            now_n = datetime.now()
                            for event in upcoming_news:
                                time_to_news = (event["time"] - now_n).total_seconds() / 60.0
                                # Si faltan menos de 10 minutos para la noticia y hay trades abiertos
                                if 0 < time_to_news <= 10.0:
                                    if self.position_manager.get_open_positions_count() > 0:
                                        self.logger.critical(f"☢️ NEWS KILLZONE: Noticia extrema '{event.get('title')}' en {time_to_news:.1f} minutos. Ejecutando Cierre Forzado para eludir GAPs.")
                                        closed_count = self.position_manager.close_all_positions(reason="Pánico Pre-Noticia")
                                        if closed_count > 0:
                                            self.telegram.notify_error(f"☢️ <b>NEWS KILLZONE</b>\nNoticia inminente en {time_to_news:.1f} min.\nSe han cerrado {closed_count} posiciones para evitar un GAP mortal.")
                    except Exception as e:
                        pass
                
                # Guardado periódico
                if datetime.now().minute % 5 == 0 and datetime.now().second < 5:
                    self._save_state()
                    
                # ─── Mantenimiento Automático (ML y Mutación) ───────
                now = datetime.now()
                # Mutación genética (Sábado a la medianoche)
                if now.weekday() == 5 and now.hour == 0 and now.minute == 0 and now.second < 30:
                    if not hasattr(self, 'last_mutation_day') or self.last_mutation_day != now.day:
                        self.logger.banner("🧬 Iniciando Auto-Mutación Genética Semanal...")
                        threading.Thread(target=self._run_genetic_optimizer, daemon=True).start()
                        self.last_mutation_day = now.day

                # Reentrenamiento de Cerebro (Domingo a la medianoche)
                if now.weekday() == 6 and now.hour == 0 and now.minute == 0 and now.second < 30:
                    if not hasattr(self, 'last_training_day') or self.last_training_day != now.day:
                        self.logger.banner("🧠 Iniciando Reentrenamiento de Cerebro IA Semanal...")
                        threading.Thread(target=self._run_ml_trainer, daemon=True).start()
                        self.last_training_day = now.day

                # ─── B. Trailing Stop, Hedging y Shadow Learning ─────────
                self.trailing_stop.update_trailing_stops()
                self.position_manager.manage_hedging()
                if hasattr(self, 'q_agent'):
                    self.q_agent.shadow_update_closed_trades()

                # ─── B.2 FRIDAY WEEKEND-KILLSWITCH ─────────────────────
                if getattr(BotConfig, "NEWS_KILLZONES_ENABLED", True): # Usando config relacionada a cierres forzosos temporales
                    from core.session_filter import get_now_institutional
                    now_ny = get_now_institutional(BotConfig.MARKET_TIMEZONE)
                    
                    if now_ny.weekday() == 4 and now_ny.hour == 16 and now_ny.minute >= 45:
                        if not getattr(self, "friday_closed", False):
                            open_pos = mt5.positions_get()
                            if open_pos and any(p.magic == BotConfig.MAGIC_NUMBER for p in open_pos):
                                self.logger.critical("🚨 VIERNES 16:45 NY - CIERRE FIN DE SEMANA. Evitando puente de liquidez o falla en FTMO.")
                                closed_wk = self.position_manager.close_all_positions(reason="Cierre Preventivo Fin de Semana")
                                self.telegram.notify_error(f"⚠️ WEEKEND KILLSWITCH: Se cerraron {closed_wk} operaciones para evitar Gaps o violación de Reglas FTMO de fin de semana.")
                            self.friday_closed = True
                            
                    if now_ny.weekday() != 4 and getattr(self, "friday_closed", False):
                        self.friday_closed = False

                # ─── C. Verificar Riesgo (Emergencia) ──────────────
                if hasattr(self.risk_manager, 'check_and_hedge_crashing_positions'):
                    self.risk_manager.check_and_hedge_crashing_positions()
                    
                if self.risk_manager.should_emergency_close():
                    daily_dd = self.risk_manager.check_daily_drawdown()
                    overall_dd = self.risk_manager.check_overall_drawdown()
                    
                    if daily_dd["level"] in ("EMERGENCY", "VIOLATED"):
                        dd_type = "DIARIO"
                        loss = daily_dd["loss"]
                        limit = daily_dd["limit"]
                    else:
                        dd_type = "TOTAL"
                        loss = overall_dd["loss"]
                        limit = overall_dd["limit"]
                        
                    self.logger.critical(f"🚨 CIERRE DE EMERGENCIA ({dd_type})")
                    self.telegram.notify_drawdown_emergency(dd_type, loss, limit)
                    closed = self.risk_manager.emergency_close_all()
                    
                    # Verificar que TODO se cerró correctamente
                    remaining = self.position_manager.get_open_positions_count()
                    if remaining > 0:
                        self.telegram._send(
                            f"🚨🚨 *ALERTA CRÍTICA* 🚨🚨\n"
                            f"⚠️ Quedan *{remaining} posiciones abiertas* después del cierre de emergencia.\n"
                            f"‼️ *CIERRA MANUALMENTE EN MT5 AHORA*"
                        )
                        self.logger.critical(f"🚨 QUEDAN {remaining} POSICIONES SIN CERRAR — INTERVENCIÓN MANUAL REQUERIDA")
                    else:
                        self.telegram._send(f"✅ Cierre de emergencia exitoso. {closed} posiciones cerradas. Bot detenido.")
                    
                    self.running = False
                    break

                # ─── C.1 Cierre Obligatorio de Fin de Semana ───────
                if self.session_filter.is_friday_forced_close_time():
                    # Evitar ejecutar cierre 2 veces si ya cerró
                    open_count = self.position_manager.get_open_positions_count()
                    if open_count > 0:
                        self.logger.critical("⏱️ CIERRE DE VIERNES (Evitando Weekend Gap)")
                        self.telegram._send(
                            f"⏱️ *CIERRE OBLIGATORIO DE VIERNES*\n"
                            f"Cerrando {open_count} posiciones para evitar gap de fin de semana..."
                        )
                        closed = self.risk_manager.emergency_close_all()
                        
                        # Verificar que todo se cerró
                        remaining = self.position_manager.get_open_positions_count()
                        if remaining > 0:
                            self.telegram._send(
                                f"🚨🚨 *PELIGRO FIN DE SEMANA* 🚨🚨\n"
                                f"⚠️ Quedan *{remaining} posiciones abiertas*\n"
                                f"‼️ *CIERRA MANUALMENTE EN MT5 ANTES DEL CIERRE DEL MERCADO*"
                            )
                            self.logger.critical(f"🚨 QUEDAN {remaining} POSICIONES ABIERTAS ENTRANDO AL FIN DE SEMANA")
                        else:
                            self.telegram._send(f"✅ Viernes: {closed} posiciones cerradas. Sin riesgo de gap.")
                    
                    # No operamos por el resto del día de todos modos
                    sleep_module.sleep(BotConfig.LOOP_INTERVAL_SECONDS)
                    continue

                # ─── D. Filtros de Trading ─────────────────────────
                # 0. Telegram Pause
                if self.is_paused:
                    sleep_module.sleep(BotConfig.LOOP_INTERVAL_SECONDS)
                    continue

                # 1. Sesión (Global)
                if not self.session_filter.is_trading_allowed():
                    sleep_module.sleep(BotConfig.LOOP_INTERVAL_SECONDS)
                    continue

                # 2. Riesgo Global (Warning Levels)
                if not self.risk_manager.is_safe_to_trade():
                    sleep_module.sleep(BotConfig.LOOP_INTERVAL_SECONDS)
                    continue

                # ─── E. Loop por Símbolo (Diversificación) ─────────
                # 🛡️ OPTIMIZACIÓN: Pedir historial de trades una vez por iteración (Previene desconexión del broker)
                cooldown_deals = None
                try:
                    cooldown_mins = getattr(BotConfig, "REVENGE_COOLDOWN_MINUTES", 30)
                    from_date_cd = datetime.now() - timedelta(minutes=cooldown_mins)
                    cooldown_deals = mt5.history_deals_get(from_date_cd, datetime.now())
                except Exception:
                    pass

                for symbol in BotConfig.WATCHLIST:
                    # Log de escaneo periódico (cada 5 min por símbolo para visibilidad)
                    now_ts = sleep_module.time()
                    if not hasattr(self, '_last_scan_log'): self._last_scan_log = {}
                    if not hasattr(self, '_last_heartbeat_log'): self._last_heartbeat_log = {}
                    if not hasattr(self, '_in_hibernation'): self._in_hibernation = False
                    if not hasattr(self, '_last_signal_found_timestamp'): self._last_signal_found_timestamp = now_ts
                    
                    if now_ts - self._last_scan_log.get(symbol, 0) > 300:
                        if not self._in_hibernation:
                            self.logger.info(f"🔍 Escaneando {symbol} (M5) | Esperando setup técnico...")
                        self._last_scan_log[symbol] = now_ts
                    
                    # ─── MODO HIBERNACIÓN LÓGICA (10 MIN) ───────────────────────
                    # Si no se detectan señales en 10 min, silenciamos los logs visuales para
                    # no saturar la consola, pero EL ESCANEO REAL DE VELAS SIGUE ACTIVO en background.
                    if now_ts - self._last_signal_found_timestamp > 600: # 10 minutos
                        if not self._in_hibernation:
                            self.logger.info("💤 MODO HIBERNACIÓN: Reduciendo spam de consola. El bot entra en escaneo silencioso en background...")
                            self._in_hibernation = True
                        
                        # Emitir un latido cada 60 minutos durante la hibernación para no parecer congelado
                        if now_ts - self._last_heartbeat_log.get(symbol, 0) > 3600:
                            self.logger.info(f"💓 HEARTBEAT: Bot activo y vigilando {symbol} en background (0 señales recientes).")
                            self._last_heartbeat_log[symbol] = now_ts
                    else:
                        self._in_hibernation = False
                    
                    try:
                        # b. Verificar Conexión con Símbolo
                        if not self.connector.ensure_symbol_available(symbol):
                            continue

                        # c. Estrategias (Multi-Strategy Loop por símbolo)
                        strategy_list = self.strategies[symbol]

                        # Solo si no hemos llenado el cupo de posiciones
                        if self.position_manager.get_open_positions_count() < BotConfig.MAX_OPEN_POSITIONS:
                            # Iterar todas las estrategias del par actual
                            for strategy in strategy_list:
                                signal = strategy.generate_signal()
                                
                                if signal:
                                    # Resetear cronómetro de hibernación al ver una señal
                                    self._last_signal_found_timestamp = sleep_module.time()
                                    if self._in_hibernation:
                                        self.logger.success("⏰ DESPERTANDO: Señal detectada. Volviendo a modo de alta frecuencia.")
                                        self._in_hibernation = False

                                    # c.1 Guardar el nombre de la estrategia que detonó el signal para logging visual
                                    signal['reason'] = f"[{strategy.get_name()}] " + signal.get('reason', '')
                                    
                                    # a. Verificar Noticias por Símbolo con IA (Alineación Técnico vs Fundamental)
                                    if getattr(BotConfig, "NEWS_KILLZONES_ENABLED", True):
                                        if not self.news_filter.is_safe_to_trade(symbol, signal['signal']):
                                            continue
                                    
                                    # d. Verificar Motor Anti-Correlación Institucional (Pearson + Net Exposure)
                                    order_type_for_corr = mt5.ORDER_TYPE_BUY if signal['signal'] == 'BUY' else mt5.ORDER_TYPE_SELL
                                    corr_allowed, corr_reason = self.correlation_manager.check_new_trade_allowed(symbol, order_type_for_corr)
                                    if not corr_allowed:
                                        continue
                                        
                                    # e. Filtro ANTI-REVENGE (Protección del Cooldown)
                                    # Consultamos directo al Broker si este símbolo tuvo alguna transacción (Apertura o Cierre) hace poco.
                                    in_cooldown = False
                                    if cooldown_deals:
                                        for d in cooldown_deals:
                                            # Solo contar CIERRES (entry=1 out, 2 reverse, 3 closeBy), NO aperturas (entry=0)
                                            if d.symbol == symbol and d.magic == BotConfig.MAGIC_NUMBER and d.entry in [1, 2, 3]:
                                                in_cooldown = True
                                                break
                                                
                                    if in_cooldown:
                                        # Log silencioso cada cierto tiempo para no llenar la consola si el signal persiste
                                        now_ts_cd = sleep_module.time()
                                        if not hasattr(self, '_last_cd_log') or now_ts_cd - self._last_cd_log.get(symbol, 0) > 60:
                                            self.logger.warning(f"⏳ COOLDOWN ACTIVO: {symbol} bloqueado por Revenge Trading ({cooldown_mins} min). Esperando que el mercado se calme.")
                                            if not hasattr(self, '_last_cd_log'): self._last_cd_log = {}
                                            self._last_cd_log[symbol] = now_ts_cd
                                        continue
                                    
                                    
                                    # SMC Detector (Order Blocks y Liquidez como Asesor Visual, no como Bloqueo)
                                    if getattr(BotConfig, "SMC_ENABLED", False):
                                        is_smc_aligned = self.smc_scanner.scan_context(symbol, signal['signal'])
                                        if is_smc_aligned:
                                            signal['reason'] += " | 🏦 SMC Confirm"
                                        else:
                                            signal['reason'] += " | ⚠️ Sin alineación SMC"
                                        
                                    # Q-Learning Agent (Intervención de Reinforcement Learning o Modo Sombra)
                                    q_state = (symbol, signal.get('adx', 20) > 18, signal['signal'])
                                
                                    if getattr(BotConfig, "Q_LEARNING_ENABLED", False):
                                        rl_action = self.q_agent.decide(q_state, signal['signal'])
                                        if rl_action == "HOLD":
                                            continue
                                        signal['signal'] = rl_action
                                    
                                    # e. Juez Supremo: ORÁCULO LLM (Gemini)
                                    if self.oracle.enabled:
                                        # 🛡️ LATENCY GUARD: Capturar precio antes de la IA
                                        tick_before = mt5.symbol_info_tick(symbol)
                                        if not tick_before:
                                            self.logger.error(f"⚠️ broker desconectado temporalmente al leer tick_before de {symbol}. Abortando trade.")
                                            continue
                                        price_before = tick_before.ask if signal['signal'] == 'BUY' else tick_before.bid
                                        
                                        # 🛡️ CRASH GUARD: Envolver llamada a IA en try/except
                                        oracle_resp = {}
                                        try:
                                            oracle_resp = self.oracle.evaluate_trade(
                                                symbol=signal['symbol'],
                                                signal_type=signal['signal'],
                                                reason=signal.get('reason', 'Análisis Quant Base'),
                                                adx=signal.get('adx', None)
                                            )
                                        except Exception as e:
                                            self.logger.error(f"⚠️ IA OFFLINE: Error evaluando trade con Gemini: {e}. Abortando por seguridad institucional.")
                                            continue
                                            
                                        # 🛡️ LATENCY GUARD: Comprobar precio después de la IA
                                        tick_after = mt5.symbol_info_tick(symbol)
                                        if not tick_after:
                                            self.logger.error(f"⚠️ broker desconectado al leer tick_after de {symbol}. Abortando trade.")
                                            continue
                                        price_after = tick_after.ask if signal['signal'] == 'BUY' else tick_after.bid
                                        
                                        # 🛡️ DYNAMIC SLIPPAGE GUARD: Máximo de 2.5 pips o 2 veces el spread
                                        symbol_info_meta = mt5.symbol_info(symbol)
                                        if not symbol_info_meta:
                                            self.logger.error(f"⚠️ broker desconectado al leer symbol_info_meta de {symbol}. Abortando trade.")
                                            continue
                                            
                                        point = symbol_info_meta.point
                                        pip_size = 10 * point
                                        # Prevenir división por cero si pip_size es 0
                                        if pip_size == 0: continue
                                        
                                        current_spread_pips = symbol_info_meta.spread * point / pip_size
                                        
                                        slippage_pips = abs(price_after - price_before) / pip_size
                                        max_allowed_slip = max(2.5, current_spread_pips * 2.0)
                                        
                                        if slippage_pips > max_allowed_slip:
                                            self.logger.warning(f"⚠️ LATENCY ABORT: El precio se deslizó {slippage_pips:.1f} pips (Max: {max_allowed_slip:.1f}) mientras la IA calculaba. Trade abortado.")
                                            continue

                                        if oracle_resp.get("decision") == "REJECTED":
                                            self.logger.warning(f"🛑 Trade Cancelado por Oráculo (CIO): {oracle_resp.get('reason')}")
                                            continue
                                        else:
                                            # Añadir la razón del oráculo al comentario del Trade
                                            signal['reason'] += f" | 𓂀 {oracle_resp.get('reason')}"
                                            signal['probability'] = oracle_resp.get('confidence', 50.0)
                                            # Taguea IA
                                            signal['strategy_tag'] = f"Gemini_{strategy.get_name()}"
                                            self.logger.success(f"✅ 🧠 ORÁCULO APROBÓ EL TRADE: {oracle_resp.get('reason')} (Slippage IA: {slippage_pips:.1f} pips)")
                                        
                                    if self.dry_run:
                                        self.logger.info(f"🔍 DRY RUN SIGNAL: {signal['signal']} {symbol}")
                                    else:
                                        # Ejecutar orden con IA Sizing (Kelly Criterion si trae probabilidad)
                                        order_type = mt5.ORDER_TYPE_BUY if signal['signal'] == 'BUY' else mt5.ORDER_TYPE_SELL
                                        probability = signal.get("probability", None)
                                    
                                        # Multiplicador Volumétrico de Portafolio
                                        port_weight = 1.0
                                        if getattr(BotConfig, "PORTFOLIO_REBALANCING", False):
                                            port_weight = self.portfolio_manager.get_weight(symbol)
                                    
                                        result = self.position_manager.place_order(
                                            symbol=signal['symbol'],
                                            order_type=order_type,
                                            stop_loss_pips=signal['stop_loss_pips'],
                                            take_profit_pips=signal['take_profit_pips'],
                                            probability=probability,
                                            portfolio_weight=port_weight,
                                            strategy_tag=signal.get('strategy_tag', f"Base_{strategy.get_name()}")
                                        )
                                    
                                        if result:
                                            # Registrar en MODO SOMBRA
                                            if hasattr(self, 'q_agent') and 'ticket' in result:
                                                self.q_agent.shadow_register_trade(result['ticket'], q_state, signal['signal'])
                                            
                                            # Registrar y Notificar
                                            acc = mt5.account_info()
                                            self.journal.record_open(
                                                order_type=signal['signal'],
                                                symbol=signal['symbol'],
                                                volume=result['volume'],
                                                price=result['price'],
                                                sl=result['sl'],
                                                tp=result['tp'],
                                                sl_pips=signal['stop_loss_pips'],
                                                tp_pips=signal['take_profit_pips'],
                                                rr_ratio=signal['take_profit_pips']/signal['stop_loss_pips'],
                                                balance=acc.balance,
                                                equity=acc.equity,
                                                daily_dd=self.risk_manager.check_daily_drawdown()["loss"],
                                                overall_dd=self.risk_manager.check_overall_drawdown()["loss"],
                                                session=self.session_filter.get_current_session(),
                                                strategy=strategy.get_name(),
                                                reason=signal.get('reason', '')
                                            )
                                            self.telegram.notify_trade_opened(
                                                order_type=signal['signal'],
                                                symbol=signal['symbol'],
                                                volume=result['volume'],
                                                price=result['price'],
                                                sl=result['sl'],
                                                tp=result['tp'],
                                                sl_pips=signal['stop_loss_pips'],
                                                tp_pips=signal['take_profit_pips'],
                                                rr_ratio=signal['take_profit_pips']/signal['stop_loss_pips']
                                            )
                                        
                                            # Si ya abrimos exitosamente un trade gracias a una estrategia con este par,
                                            # salimos del loop de estrategias interno para no saturar 2 trades en el mismo lugar al mismo instante.
                                            break
                                        else:
                                            import json
                                            if self.oracle.enabled:
                                                # El broker lo rechazó, actualizar dashboard
                                                try:
                                                    self.oracle.last_narration = json.dumps({
                                                        "decision": "BLOCKED (BROKER)",
                                                        "reason": f"La IA APROBÓ el trade en {signal['symbol']}, pero el Sistema de Riesgo Automático de MT5 lo rechazó (Spread superior a lo permitido). Protegiendo tu balance de ejecuciones peligrosas.",
                                                        "confidence": probability if probability else 0
                                                    })
                                                except Exception:
                                                    pass
                    except Exception as e:
                        import traceback
                        self.logger.error(f"Error procesando {symbol}: {e}\n{traceback.format_exc()}")
                        continue

                # ─── F. Verificar Fase Completada ──────────────────
                status = self.phase_tracker.check_phase_complete()
                if status["complete"]:
                    self.telegram.notify_phase_complete(self.phase, status["current_profit"], status["profitable_days"])
                    self.running = False
                    break

                sleep_module.sleep(BotConfig.LOOP_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                self.logger.error(f"Error en loop principal: {e}")
                self.telegram.notify_error(str(e))
                sleep_module.sleep(10)

        self._shutdown()

    def _shutdown(self):
        """Cierre limpio"""
        self.logger.banner("🛑 DETENIENDO BOT")
        self._save_state()
        
        try:
            acc = self.connector.get_account_info()
            if acc:
                self.telegram.notify_bot_stopped("Shutdown manual", acc['balance'], acc['profit'])
        except Exception:
            pass
        
        self.connector.disconnect()
        self.logger.info("Bot apagado correctamente. Bye! 👋")

    def _run_watchdog_loop(self):
        """
        Hilo secundario que vigila si el loop principal está 'vivo'.
        Si el loop principal se congela por más de 30 min, envía alerta.
        """
        self.logger.info("🛡️ Watchdog System activo (Vigilancia 24/7)")
        while self.running:
            sleep_module.sleep(300) # Chequear cada 5 min
            
            inactivity_seconds = sleep_module.time() - self._last_loop_timestamp
            
            # Si han pasado más de 10 min sin actividad en el loop
            if inactivity_seconds > 600:
                if not self._watchdog_notified:
                    msg = "🚨 ALERTA CRÍTICA: El loop principal del bot no responde desde hace +10 min. Posible congelamiento detectado."
                    self.logger.critical(msg)
                    self.telegram.notify_error(msg)
                    self._watchdog_notified = True
            else:
                # Resetear notificación si el loop volvió a la vida
                self._watchdog_notified = False


def main():
    import traceback
    parser = argparse.ArgumentParser(description="TX3 Pro Bot Professional")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True, help="1 or 2")
    parser.add_argument("--dry-run", action="store_true", help="Simulation mode")
    args = parser.parse_args()

    bot = TX3ProBot(phase=args.phase, dry_run=args.dry_run)
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.logger.info("Cierre por Teclado (Ctrl+C).")
    except SystemExit:
        bot.logger.info("Cierre del Sistema/Terminal detectado.")
        bot.telegram.notify_error("🛑 FATAL: La terminal del bot fue cerrada por el sistema operativo (Crash o VPS reiniciado).")
    except Exception as e:
        crash_log = traceback.format_exc()
        bot.logger.error(f"CRASH FATAL:\n{crash_log}")
        bot.telegram.notify_error(f"💀 CRASH FATAL DEL BOT: El programa en Python colapsó.\nError: {e}")
    except BaseException as e:
        bot.telegram.notify_error(f"🛑 ATENCIÓN ROJA: La ventana (terminal negra) ha sido CERRADA o matada a la fuerza en el VPS.")
    finally:
        # Intentar último respiro de notificación al forzar el cierre
        try:
            if bot.running: # Si sigue encendido mágicamente pero está muriendo, avisa.
                bot.telegram.notify_bot_stopped("Cierre Inesperado/Forzado de la terminal", 0, 0)
        except:
            pass

if __name__ == "__main__":
    main()
