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

import MetaTrader5 as mt5

from config.settings import ChallengeConfig, BotConfig, DashboardConfig, TelegramConfig
from core.risk_manager import RiskManager
from core.position_manager import PositionManager
from core.phase_tracker import PhaseTracker
from core.session_filter import SessionFilter
from core.news_filter import NewsFilter
from core.trailing_stop import TrailingStopManager
from strategy.ema_cross import EMACrossStrategy
from utils.logger import BotLogger
from utils.mt5_connector import MT5Connector
from utils.telegram_notifier import TelegramNotifier
from utils.trade_journal import TradeJournal
from utils.state_manager import StateManager
from dashboard.app import run_dashboard, update_dashboard_data, add_dashboard_log


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

        # ─── Inicializar componentes ─────────────────────────────────
        self.logger = BotLogger(name="TX3Bot")
        self.connector = MT5Connector(logger=self.logger)
        
        # Notificaciones y Persistencia
        self.telegram = TelegramNotifier(logger=self.logger)
        self.state_manager = StateManager(logger=self.logger)
        self.journal = TradeJournal(logger=self.logger, phase=phase)

        # Core Logic
        self.risk_manager = RiskManager(logger=self.logger)
        self.position_manager = PositionManager(logger=self.logger, phase=phase)
        self.phase_tracker = PhaseTracker(logger=self.logger, phase=phase)
        self.session_filter = SessionFilter(logger=self.logger)
        
        # Pro Features
        self.news_filter = NewsFilter(logger=self.logger)
        self.trailing_stop = TrailingStopManager(logger=self.logger)
        
        # Pro Features
        self.news_filter = NewsFilter(logger=self.logger)
        self.trailing_stop = TrailingStopManager(logger=self.logger)
        
        # Estrategias (Multi-Symbol Optimization)
        self.strategies = {}
        for symbol in BotConfig.WATCHLIST:
            self.strategies[symbol] = EMACrossStrategy(logger=self.logger, symbol=symbol)
            self.logger.info(f"✅ Estrategia cargada: {symbol}")

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
        
        # Formatear posiciones para JSON
        pos_list = []
        for p in positions:
            pos_list.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "profit": p.profit,
                "sl": p.sl,
                "tp": p.tp
            })

        data = {
            "status": "RUNNING" if self.running else "STOPPED",
            "phase": self.phase,
            "balance": account["balance"] if account else 0,
            "equity": account["equity"] if account else 0,
            "daily_profit": self.phase_tracker.current_day_profit,
            "daily_dd": daily_dd["loss"],
            "overall_dd": overall_dd["loss"],
            "open_positions": pos_list,
            "last_update": datetime.now().strftime("%H:%M:%S")
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
        self.telegram.notify_bot_started(
            phase=self.phase,
            dry_run=self.dry_run,
            balance=real_balance if account_info else 0,
            watchlist=BotConfig.WATCHLIST,
        )

        self.running = True
        
        while self.running:
            try:
                # ─── A. Monitoreo y Mantenimiento ──────────────────
                if not self.connector.is_connected():
                    self.logger.warning("Intentando reconexión a MT5...")
                    if not self.connector.connect():
                        sleep_module.sleep(30)
                        continue
                
                self.phase_tracker.update_daily_profit()
                self._check_daily_reset()
                self._update_dashboard()
                
                # Guardado periódico
                if datetime.now().minute % 5 == 0 and datetime.now().second < 5:
                    self._save_state()

                # ─── B. Trailing Stop ──────────────────────────────
                self.trailing_stop.update_trailing_stops()

                # ─── C. Verificar Riesgo (Emergencia) ──────────────
                if self.risk_manager.should_emergency_close():
                    self.logger.critical("🚨 CIERRE DE EMERGENCIA")
                    self.telegram.notify_drawdown_emergency("TOTAL", 0, 0)
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
                        # a. Verificar Noticias por Símbolo
                        if not self.news_filter.is_safe_to_trade(symbol):
                            continue
                        
                        # b. Verificar Conexión con Símbolo
                        if not self.connector.ensure_symbol_available(symbol):
                            continue

                        # c. Estrategia
                        # Instanciar estrategia temporalmente o usar un dict de estrategias
                        # Para simpleza, instanciamos aquí (ligero overhead, pero seguro)
                        # strategy = EMACrossStrategy(logger=self.logger, symbol=symbol) # Removed temporary strategy instantiation
                        strategy = self.strategies[symbol] # Use pre-initialized strategy from dictionary

                        # Solo si no hemos llenado el cupo de posiciones
                        if self.position_manager.get_open_positions_count() < BotConfig.MAX_OPEN_POSITIONS:
                            signal = strategy.generate_signal()
                            
                            if signal:
                                if self.dry_run:
                                    self.logger.info(f"🔍 DRY RUN SIGNAL: {signal['signal']} {symbol}")
                                else:
                                    # Ejecutar orden
                                    order_type = mt5.ORDER_TYPE_BUY if signal['signal'] == 'BUY' else mt5.ORDER_TYPE_SELL
                                    
                                    result = self.position_manager.place_order(
                                        symbol=signal['symbol'],
                                        order_type=order_type,
                                        stop_loss_pips=signal['stop_loss_pips'],
                                        take_profit_pips=signal['take_profit_pips']
                                    )
                                    
                                    if result:
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
                    except Exception as e:
                        self.logger.error(f"Error procesando {symbol}: {e}")
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
    parser = argparse.ArgumentParser(description="TX3 Pro Bot Professional")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True, help="1 or 2")
    parser.add_argument("--dry-run", action="store_true", help="Simulation mode")
    args = parser.parse_args()

    bot = TX3ProBot(phase=args.phase, dry_run=args.dry_run)
    bot.run()


if __name__ == "__main__":
    main()
