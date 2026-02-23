"""
📝 Sistema de Logging del Bot
==============================
Logging profesional con colores, timestamps y guardado a archivo.
"""

import logging
import os
from datetime import datetime


class BotLogger:
    """Logger centralizado para el bot de trading"""

    # Colores ANSI para la terminal
    COLORS = {
        "RESET": "\033[0m",
        "RED": "\033[91m",
        "GREEN": "\033[92m",
        "YELLOW": "\033[93m",
        "BLUE": "\033[94m",
        "MAGENTA": "\033[95m",
        "CYAN": "\033[96m",
        "WHITE": "\033[97m",
        "BOLD": "\033[1m",
    }

    def __init__(self, name: str = "TX3Bot", log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir

        # Crear directorio de logs
        os.makedirs(log_dir, exist_ok=True)

        # Configurar logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # Handler para archivo
        log_filename = f"{log_dir}/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        self.logger.addHandler(file_handler)

        # Handler para consola (con colores)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter("%(message)s")
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)

        self.info(f"📝 Logger inicializado -> {log_filename}")

    def _colorize(self, text: str, color: str) -> str:
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    # ─── Métodos de logging ───────────────────────────────────────────

    def info(self, message: str):
        colored = self._colorize(f"ℹ️  {message}", "CYAN")
        self.logger.info(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def success(self, message: str):
        colored = self._colorize(f"✅ {message}", "GREEN")
        self.logger.info(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def warning(self, message: str):
        colored = self._colorize(f"⚠️  {message}", "YELLOW")
        self.logger.warning(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def error(self, message: str):
        colored = self._colorize(f"❌ {message}", "RED")
        self.logger.error(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def critical(self, message: str):
        colored = self._colorize(f"🚨 {message}", "RED")
        self.logger.critical(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def trade(self, message: str):
        colored = self._colorize(f"📊 {message}", "MAGENTA")
        self.logger.info(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def risk(self, message: str):
        colored = self._colorize(f"🛡️  {message}", "YELLOW")
        self.logger.info(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def phase(self, message: str):
        colored = self._colorize(f"🎯 {message}", "BLUE")
        self.logger.info(colored)
        from dashboard.app import add_dashboard_log
        add_dashboard_log(colored)

    def separator(self, char: str = "─", length: int = 60):
        line = char * length
        self.logger.info(self._colorize(line, "WHITE"))

    def banner(self, title: str):
        self.separator("═")
        self.logger.info(self._colorize(f"  {title}", "BOLD"))
        self.separator("═")

    # ─── Logging de estado ────────────────────────────────────────────

    def log_drawdown_status(
        self,
        daily_loss: float,
        daily_limit: float,
        overall_loss: float,
        overall_limit: float,
    ):
        """Log del estado de drawdown"""
        daily_pct = (daily_loss / daily_limit) * 100 if daily_limit > 0 else 0
        overall_pct = (overall_loss / overall_limit) * 100 if overall_limit > 0 else 0

        self.separator()
        self.risk("ESTADO DE DRAWDOWN")
        self.risk(
            f"  Diario: -${daily_loss:>8.2f} / -${daily_limit:>8.2f}  "
            f"({daily_pct:5.1f}%)  Margen: ${daily_limit - daily_loss:>8.2f}"
        )
        self.risk(
            f"  Total:  -${overall_loss:>8.2f} / -${overall_limit:>8.2f}  "
            f"({overall_pct:5.1f}%)  Margen: ${overall_limit - overall_loss:>8.2f}"
        )

    def log_phase_progress(
        self,
        phase: int,
        current_profit: float,
        target: float,
        profitable_days: int,
        min_days: int,
    ):
        """Log del progreso de la fase"""
        profit_pct = (current_profit / target) * 100 if target > 0 else 0

        self.separator()
        self.phase(f"PROGRESO FASE {phase}")
        self.phase(
            f"  Profit:     ${current_profit:>8.2f} / ${target:>8.2f}  "
            f"({profit_pct:5.1f}%)  {'✅' if current_profit >= target else '❌'}"
        )
        self.phase(
            f"  Días rent.: {profitable_days}/{min_days}  "
            f"{'✅' if profitable_days >= min_days else '❌'}"
        )

    def log_order(
        self,
        order_type: str,
        symbol: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        sl_pips: float,
        tp_pips: float,
    ):
        """Log de una orden ejecutada"""
        self.separator()
        self.trade("ORDEN EJECUTADA")
        self.trade(f"  Tipo:     {order_type}")
        self.trade(f"  Símbolo:  {symbol}")
        self.trade(f"  Volumen:  {volume:.2f} lotes")
        self.trade(f"  Precio:   {price:.5f}")
        self.trade(f"  SL:       {sl:.5f} (-{sl_pips:.1f} pips)")
        self.trade(f"  TP:       {tp:.5f} (+{tp_pips:.1f} pips)")
