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
from datetime import datetime
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
from strategy.bollinger_rsi import BollingerRSIStrategy
from strategy.ny_opening_breakout import NYOpeningBreakoutStrategy
from strategy.tokyo_opening_breakout import TokyoOpeningBreakoutStrategy
from strategy.london_opening_breakout import LondonOpeningBreakoutStrategy
from strategy.sydney_opening_breakout import SydneyOpeningBreakoutStrategy
from utils.logger import BotLogger
from utils.mt5_connector import MT5Connector
from utils.telegram_notifier import TelegramNotifier
from utils.trade_journal import TradeJournal
from utils.state_manager import StateManager
from dashboard.app import run_dashboard, update_dashboard_data, add_dashboard_log
from utils.telegram_commands import TelegramCommandHandler
from core.smc_scanner import SMCScanner
from core.portfolio_manager import PortfolioManager
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
        self.trailing_stop = TrailingStopManager(logger=self.logger)
        self.oracle = GeminiOracle(logger=self.logger)
        
        # Next-Gen Institutional features
        self.smc_scanner = SMCScanner(logger=self.logger)
        self.portfolio_manager = PortfolioManager(logger=self.logger)
        self.q_agent = QLearningAgent(logger=self.logger)
        
        # Estrategias (Multi-Symbol Optimization + Multi-Strategy)
        self.strategies = {}
        for symbol in BotConfig.WATCHLIST:
            self.strategies[symbol] = [
                BollingerRSIStrategy(logger=self.logger, symbol=symbol),
                NYOpeningBreakoutStrategy(logger=self.logger, symbol=symbol),
                LondonOpeningBreakoutStrategy(logger=self.logger, symbol=symbol),
                TokyoOpeningBreakoutStrategy(logger=self.logger, symbol=symbol),
                SydneyOpeningBreakoutStrategy(logger=self.logger, symbol=symbol)
            ]
            self.logger.info(f"✅ Todas las estrategias [Bull/Bear+RSI, NY, LND, TKY, SYN Breakouts] cargadas en: {symbol}")

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
                
                # Restaurar balance inicial real (capturado de MT5)
                saved_balance = state.get("balance_inicial", 0)
                if saved_balance > 0:
                    self.risk_manager.balance_inicial = saved_balance
                    self.phase_tracker.balance_inicial = saved_balance
                
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

        # Calcular trades de hoy desde el historial (asumiendo que las fechas en timestamps concuerdan)
        today_str = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        recent_trades = self.journal.get_recent_trades(limit=50)
        trades_hoy = len([t for t in recent_trades if t.get('timestamp', '').startswith(today_str)])
        
        # O usar el mayor entre el journal y el de memoria
        total_trades_display = max(trades_hoy, self.position_manager.trades_today)

        data = {
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
            "overall_dd": overall_dd["loss"],
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
            "last_update": datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
        }
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
        
        # Esperar 5 minutos al iniciar antes de hacer el primer chequeo
        time.sleep(300)
        
        while self.running:
            try:
                # Recopilar métricas
                uptime_str = "Desconocido"
                if hasattr(self.telegram_commands, "_start_time"):
                    delta = datetime.now() - self.telegram_commands._start_time
                    hours, remainder = divmod(int(delta.total_seconds()), 3600)
                    minutes, _ = divmod(remainder, 60)
                    uptime_str = f"{hours}h {minutes}m"
                    
                hours_since_last = "Desconocido"
                hours_diff = 0
                try:
                    import MetaTrader5 as mt5
                    now = datetime.now()
                    back = now - timedelta(days=7)
                    deals = mt5.history_deals_get(back, now)
                    if deals and len(deals) > 0:
                        last_deal_time = datetime.fromtimestamp(deals[-1].time)
                        hours_diff = (now - last_deal_time).total_seconds() / 3600
                        hours_since_last = f"{hours_diff:.1f}"
                except Exception:
                    pass
                    
                daily_dd = self.risk_manager.check_daily_drawdown()["loss"]
                overall_dd = self.risk_manager.check_overall_drawdown()["loss"]
                
                # Criterios de Emergencia
                is_emergency = False
                trigger_reason = ""
                
                if hours_diff > 24:
                    is_emergency = True
                    trigger_reason = "⚠️ Inactividad Prolongada (>24h sin trades)"
                elif overall_dd > (ChallengeConfig.MAX_OVERALL_DRAWDOWN * 0.5):
                    is_emergency = True
                    trigger_reason = "📉 Drawdown Crítico Acumulado"
                    
                if is_emergency:
                    self.logger.warning(f"🩺 Dr. Quant detectó una anomalía ({trigger_reason}). Consultando Oráculo...")
                    metrics = {
                        "uptime": uptime_str,
                        "hours_since_last_trade": hours_since_last,
                        "daily_dd": daily_dd,
                        "overall_dd": overall_dd,
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
            # 1. Verificar MT5
            if self.connector.is_connected():
                acc = mt5.account_info()
                if acc:
                    self.logger.success(f"🔹 MT5: Conectado a Cuenta {acc.login} ({acc.company})")
                    checklist["Conexión MT5"] = True
            
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
            # Si no hay estado guardado previo, usar el balance real de MT5
            # como referencia en lugar del valor fijo de ChallengeConfig
            state = self.state_manager.load_state()
            if state and state.get("balance_inicial", 0) > 0:
                # Restaurar el balance inicial guardado previamente
                initial_ref = state["balance_inicial"]
                self.logger.info(f"💾 Balance inicial restaurado: ${initial_ref:,.2f}")
            else:
                # Primera ejecución: usar balance actual de MT5
                initial_ref = real_balance
                self.logger.info(f"🆕 Balance inicial capturado de MT5: ${initial_ref:,.2f}")
            
            # Propagar a todos los módulos
            self.risk_manager.balance_inicial = initial_ref
            self.phase_tracker.balance_inicial = initial_ref
            
            # Setup equity inicio día si es necesario
            if self.risk_manager.equity_inicio_dia == ChallengeConfig.BALANCE_INICIAL:
                self.risk_manager.equity_inicio_dia = max(real_balance, account_info.equity)
        
        self._print_startup_banner()
        
        # 🧪 PRE-FLIGHT DIAGNOSTICS (Auto-Prueba de Sistemas)
        if not self.run_preflight_checks():
            self.logger.critical("🛑 AUTO-PRUEBA FALLIDA: El bot no puede iniciar con errores críticos.")
            self.telegram.notify_error("🚨 FALLO DE INICIO: Auto-prueba técnica fallida. Revisa los logs.")
            return

        # 🩺 SINCRONIZACIÓN INICIAL DE HISTORIAL (Consistencia Dashboard)
        try:
            from datetime import datetime, timedelta
            now = datetime.now()
            # Ventana de 24 horas para cubrir cualquier zona horaria del broker
            sync_start = now - timedelta(hours=24)
            deals_sync = mt5.history_deals_get(sync_start, now + timedelta(hours=1))
            if deals_sync:
                self.journal.sync_mt5_history(deals_sync)
        except Exception as e:
            self.logger.warning(f"No se pudo sincronizar historial inicial: {e}")

        self.telegram.notify_bot_started(
            phase=self.phase,
            dry_run=self.dry_run,
            balance=real_balance if account_info else 0,
            watchlist=BotConfig.WATCHLIST,
        )

        self.running = True
        self._notified_disconnect = False
        reconnect_attempts = 0
        
        while self.running:
            try:
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
                
                # Sincronizar trades cerrados por el broker (SL/TP/Trailing)
                try:
                    today = datetime.now()
                    start_today = datetime(today.year, today.month, today.day)
                    from datetime import timedelta
                    deals_sync = mt5.history_deals_get(start_today, today + timedelta(days=1))
                    if deals_sync:
                        new_trades = self.journal.sync_mt5_history(deals_sync)
                        if new_trades:
                            for trade in new_trades:
                                self.telegram.notify_trade_closed(
                                    symbol=trade.get("symbol", "N/A"),
                                    order_type=trade.get("type", "N/A"),
                                    volume=trade.get("volume", 0.0),
                                    profit=trade.get("profit", 0.0),
                                    pips=trade.get("pips", 0.0),
                                    duration="MT5 Sync"
                                )
                except Exception as e:
                    pass

                self.phase_tracker.update_daily_profit()
                self._check_daily_reset()
                self._update_dashboard()
                
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

                # ─── B.1 AI Exit Engine (Salidas Inteligentes) ─────────
                if self.oracle.enabled:
                    current_min = datetime.now().minute
                    for p in self.position_manager.get_open_positions():
                        # Solo analiza si es ganadora (Ahorro estricto de cuota API)
                        if p.profit > 0:
                            si = mt5.symbol_info(p.symbol)
                            pip_size = 0.01 if "JPY" in p.symbol else 0.0001
                            tick = mt5.symbol_info_tick(p.symbol)
                            
                            pips_profit = 0.0
                            if tick and si:
                                if p.type == mt5.ORDER_TYPE_BUY:
                                    pips_profit = (tick.bid - p.price_open) / pip_size
                                else:
                                    pips_profit = (p.price_open - tick.ask) / pip_size
                                    
                            # Empieza a evaluar solo si hay más de 5 pips de ganancia
                            if pips_profit >= 5.0:
                                t_type = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                                
                                # Consultar solo en cierres de vela de 15 minutos (0, 15, 30, 45)
                                if current_min % 15 == 0:
                                    if not hasattr(self, "last_ai_exit_checks"):
                                        self.last_ai_exit_checks = {}
                                    
                                    last_chk = self.last_ai_exit_checks.get(p.ticket, -1)
                                    if last_chk != current_min:
                                        self.last_ai_exit_checks[p.ticket] = current_min
                                        decision = self.oracle.evaluate_exit(p.symbol, pips_profit, t_type)
                                        if decision.get("decision") == "CLOSE":
                                            self.logger.success(f"🤖🧠 ORÁCULO ORDENA CIERRE ANTICIPADO: Ticket #{p.ticket} | Razón: {decision.get('reason')}")
                                            self.position_manager.close_position(p.ticket)
                                            if hasattr(self.telegram, 'chat_id'):
                                                self.telegram._send_message(self.telegram.chat_id, f"🤖🧠 *CIA (Salida Inteligente)*\nCierre Anticipado en {p.symbol} (+{pips_profit:.1f} pips)\nRazón: {decision.get('reason')}")

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
                    self.risk_manager.emergency_close_all()
                    self.running = False
                    break

                # ─── C.1 Cierre Obligatorio de Fin de Semana ───────
                if self.session_filter.is_friday_forced_close_time():
                    # Evitar ejecutar cierre 2 veces si ya cerró
                    if self.position_manager.get_open_positions_count() > 0:
                        self.logger.critical("⏱️ CIERRE DE VIERNES (Evitando Weekend Hold)")
                        self.telegram.notify_error("⏱️ CIERRE OBLIGATORIO DE VIERNES EJECUTADO")
                        self.risk_manager.emergency_close_all() # Reutilizamos la función de emergencia para cerrar todo
                    
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
                for symbol in BotConfig.WATCHLIST:
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
                                    # c.1 Guardar el nombre de la estrategia que detonó el signal para logging visual
                                    signal['reason'] = f"[{strategy.get_name()}] " + signal.get('reason', '')
                                    
                                    # a. Verificar Noticias por Símbolo con IA (Alineación Técnico vs Fundamental)
                                    if getattr(BotConfig, "NEWS_KILLZONES_ENABLED", True):
                                        if not self.news_filter.is_safe_to_trade(symbol, signal['signal']):
                                            continue
                                    
                                    # d. Verificar Escudo Anti-Correlación (Evitar pares múltiples muy atados)
                                    if not self.position_manager.check_correlation_shield(symbol):
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
                                        oracle_resp = self.oracle.evaluate_trade(
                                            symbol=signal['symbol'],
                                            signal_type=signal['signal'],
                                            reason=signal.get('reason', 'Análisis Quant Base'),
                                            adx=signal.get('adx', None)
                                        )
                                        if oracle_resp.get("decision") == "REJECTED":
                                            self.logger.warning(f"🛑 Trade Cancelado por Oráculo (CIO): {oracle_resp.get('reason')}")
                                            continue
                                        else:
                                            # Añadir la razón del oráculo al comentario del Trade
                                            signal['reason'] += f" | 𓂀 {oracle_resp.get('reason')}"
                                            signal['probability'] = oracle_resp.get('confidence', 50.0)
                                            # Taguea IA
                                            signal['strategy_tag'] = f"Gemini_{strategy.get_name()}"
                                        
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
