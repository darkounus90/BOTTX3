"""
📱 Telegram Notifier - Notificaciones en Tiempo Real
======================================================
Envía notificaciones a Telegram cuando:
- Se inicia o detiene el bot
- Se ejecuta/cierra un trade
- Drawdown llega a niveles de alerta/emergencia
- Se completa una fase
- Resumen diario
- Errores críticos
- Reconexión a MT5
"""

import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from config.settings import TelegramConfig
from utils.logger import BotLogger


class TelegramNotifier:
    """
    Envía notificaciones al chat de Telegram configurado.
    Usa la API REST directa para evitar dependencias de async.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.enabled = TelegramConfig.ENABLED
        self.token = TelegramConfig.BOT_TOKEN
        self.chat_id = TelegramConfig.CHAT_ID
        self._start_time = datetime.now(ZoneInfo("America/New_York"))

        if self.enabled and (not self.token or not self.chat_id):
            self.enabled = False
            self.logger.warning(
                "Telegram deshabilitado: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID"
            )
        elif self.enabled:
            self.logger.success("Telegram Notifier activado ✅")

    def _send(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Envía un mensaje a Telegram"""
        if not self.enabled:
            return False

        try:
            url = self.BASE_URL.format(token=self.token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code != 200:
                self.logger.error(f"Telegram error: {response.status_code} - {response.text}")
                return False

            return True

        except requests.exceptions.Timeout:
            self.logger.error("Telegram: timeout al enviar mensaje")
            return False
        except Exception as e:
            self.logger.error(f"Telegram error: {str(e)}")
            return False

    # ─── Notificaciones de Estado del Bot ──────────────────────────────

    def notify_bot_started(
        self,
        phase: int,
        dry_run: bool,
        balance: float,
        watchlist: list,
    ):
        """Notifica que el bot se inició correctamente"""
        mode = "🔍 SIMULACIÓN" if dry_run else "🟢 EN VIVO"
        symbols = ", ".join(watchlist) if watchlist else "N/A"

        msg = (
            f"🚀 *BOT INICIADO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 Fase: *{phase}*\n"
            f"🎮 Modo: *{mode}*\n"
            f"💰 Balance: `${balance:,.2f}`\n"
            f"📊 Pares: `{symbols}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Todos los sistemas operativos\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self._send(msg)

    def notify_bot_stopped(self, reason: str, balance: float, profit: float):
        """Notifica que el bot se detuvo"""
        # Calcular tiempo de ejecución
        uptime = datetime.now(ZoneInfo("America/New_York")) - self._start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m"

        profit_sign = "+" if profit >= 0 else ""
        profit_emoji = "📈" if profit >= 0 else "📉"

        msg = (
            f"🛑 *BOT DETENIDO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 Razón: _{reason}_\n"
            f"💰 Balance final: `${balance:,.2f}`\n"
            f"{profit_emoji} P&L sesión: `{profit_sign}${profit:,.2f}`\n"
            f"⏱ Tiempo activo: `{uptime_str}`\n"
            f"🕐 {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self._send(msg)

    def notify_reconnection(self, attempt: int):
        """Notifica que el bot se reconectó a MT5"""
        msg = (
            f"🔄 *RECONEXIÓN MT5*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Conexión restablecida\n"
            f"🔁 Intento: `#{attempt}`\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)

    # ─── Notificaciones de Trading ────────────────────────────────────

    def notify_trade_opened(
        self,
        order_type: str,
        symbol: str,
        volume: float,
        price: float,
        sl: float,
        tp: float,
        sl_pips: float,
        tp_pips: float,
        rr_ratio: float,
    ):
        """Notifica que se abrió un trade"""
        if not TelegramConfig.NOTIFY_ON_TRADE:
            return

        emoji = "🟢" if order_type == "BUY" else "🔴"
        direction = "COMPRA" if order_type == "BUY" else "VENTA"

        msg = (
            f"{emoji} *TRADE ABIERTO — {direction}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Par: *{symbol}*\n"
            f"📦 Volumen: `{volume:.2f}` lotes\n"
            f"💰 Entrada: `{price:.5f}`\n"
            f"🛑 SL: `{sl:.5f}` (`-{sl_pips:.0f}` pips)\n"
            f"🎯 TP: `{tp:.5f}` (`+{tp_pips:.0f}` pips)\n"
            f"⚖️ Riesgo/Beneficio: `1:{rr_ratio:.1f}`\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)

    def notify_trade_closed(
        self,
        symbol: str,
        order_type: str,
        volume: float,
        profit: float,
        pips: float,
        duration: str,
    ):
        """Notifica que se cerró un trade"""
        if not TelegramConfig.NOTIFY_ON_CLOSE:
            return

        if profit >= 0:
            emoji = "✅"
            result = "GANANCIA"
        else:
            emoji = "❌"
            result = "PÉRDIDA"

        profit_sign = "+" if profit >= 0 else ""

        msg = (
            f"{emoji} *TRADE CERRADO — {result}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 {order_type} *{symbol}* (`{volume:.2f}` lots)\n"
            f"💰 Resultado: `{profit_sign}${profit:.2f}`\n"
            f"📏 Pips: `{profit_sign}{pips:.1f}`\n"
            f"⏱ Duración: `{duration}`\n"
            f"🕐 {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)

    # ─── Notificaciones de Riesgo ─────────────────────────────────────

    def notify_drawdown_warning(self, dd_type: str, loss: float, limit: float, pct: float):
        """Notifica alerta de drawdown (70%)"""
        if not TelegramConfig.NOTIFY_ON_DD_WARNING:
            return

        dd_label = "DIARIO" if dd_type.upper() == "DAILY" else "TOTAL"
        remaining = limit - loss

        msg = (
            f"⚠️ *ALERTA DRAWDOWN {dd_label}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 Pérdida actual: `${loss:,.2f}`\n"
            f"🚧 Límite máximo: `${limit:,.2f}`\n"
            f"📊 Nivel: `{pct:.1f}%` del límite\n"
            f"🛡️ Margen restante: `${remaining:,.2f}`\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)

    def notify_drawdown_emergency(self, dd_type: str, loss: float, limit: float):
        """Notifica emergencia de drawdown (85%) — cierre total"""
        if not TelegramConfig.NOTIFY_ON_DD_EMERGENCY:
            return

        dd_label = "DIARIO" if dd_type.upper() == "DAILY" else "TOTAL"

        msg = (
            f"🚨🚨🚨 *EMERGENCIA DRAWDOWN {dd_label}* 🚨🚨🚨\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 Pérdida: `${loss:,.2f}` / `${limit:,.2f}`\n"
            f"⚡ CERRANDO TODAS LAS POSICIONES\n"
            f"🛑 Bot detenido por seguridad\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ _Revisa tu cuenta antes de reiniciar_\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)

    # ─── Notificaciones de Fase ───────────────────────────────────────

    def notify_phase_complete(self, phase: int, profit: float, days: int):
        """Notifica que se completó una fase"""
        if not TelegramConfig.NOTIFY_ON_PHASE_COMPLETE:
            return

        if phase == 1:
            next_step = "▶️ Siguiente paso: *Fase 2* (5% target)"
        else:
            next_step = "💰 *¡CUENTA FONDEADA!*\n🎁 Solicita tu primer payout"

        msg = (
            f"🎉🎉🎉 *¡FASE {phase} COMPLETADA!* 🎉🎉🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Profit total: `+${profit:,.2f}`\n"
            f"📅 Días rentables: `{days}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{next_step}\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self._send(msg)

    # ─── Resumen Diario ───────────────────────────────────────────────

    def notify_daily_summary(
        self,
        phase: int,
        day_profit: float,
        total_profit: float,
        profit_target: float,
        profitable_days: int,
        min_days: int,
        daily_dd: float,
        overall_dd: float,
        trades_today: int,
        win_rate: float,
    ):
        """Envía el resumen diario"""
        if not TelegramConfig.NOTIFY_DAILY_SUMMARY:
            return

        p_emoji = "📈" if day_profit >= 0 else "📉"
        day_sign = "+" if day_profit >= 0 else ""
        progress_pct = (total_profit / profit_target * 100) if profit_target > 0 else 0

        # Barra de progreso visual
        filled = int(progress_pct / 10)
        bar = "▓" * min(filled, 10) + "░" * max(10 - filled, 0)

        msg = (
            f"📋 *RESUMEN DIARIO — FASE {phase}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{p_emoji} Hoy: `{day_sign}${day_profit:,.2f}`\n"
            f"💰 Total: `${total_profit:,.2f}` / `${profit_target:,.2f}`\n"
            f"📊 Progreso: `[{bar}]` `{progress_pct:.0f}%`\n"
            f"📅 Días rentables: `{profitable_days}/{min_days}`\n"
            f"🔢 Trades hoy: `{trades_today}` | Win rate: `{win_rate:.0f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📉 DD diario: `${daily_dd:,.2f}` / `$2,500`\n"
            f"📉 DD total: `${overall_dd:,.2f}` / `$5,000`\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M')}"
        )
        self._send(msg)

    # ─── Errores ──────────────────────────────────────────────────────

    def notify_error(self, error_message: str):
        """Notifica un error crítico"""
        if not TelegramConfig.NOTIFY_ON_ERROR:
            return

        msg = (
            f"❌ *ERROR CRÍTICO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"`{error_message[:500]}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ _El bot continúa operando_\n"
            f"⏱ {datetime.now(ZoneInfo('America/New_York')).strftime('%H:%M:%S')}"
        )
        self._send(msg)
