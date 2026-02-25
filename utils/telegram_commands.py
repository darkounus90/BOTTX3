import time
import threading
import requests
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from config.settings import TelegramConfig, ChallengeConfig
from utils.logger import BotLogger


class TelegramCommandHandler:
    """
    Control Remoto por Telegram.
    Corre en un thread separado usando polling con getUpdates
    de la API REST de Telegram.
    """

    def __init__(self, logger: BotLogger, bot_reference):
        self.logger = logger
        self.bot = bot_reference
        self.enabled = TelegramConfig.ENABLED
        self.token = TelegramConfig.BOT_TOKEN
        self.chat_id = str(TelegramConfig.CHAT_ID)
        self.url_base = f"https://api.telegram.org/bot{self.token}/"
        self.offset = None
        self.running = False
        self.thread = None

    def start(self):
        """Inicia el thread de polling de comandos"""
        if not self.enabled or not self.token or not self.chat_id:
            self.logger.warning("Telegram Commands deshabilitado: faltan credenciales")
            return
            
        self.running = True
        self._start_time = datetime.now()
        self.thread = threading.Thread(target=self._poll_updates, daemon=True)
        self.thread.start()
        self.logger.success("📡 Telegram Command Handler iniciado (Polling)")

    def stop(self):
        """Detiene el thread de polling"""
        self.running = False

    def _poll_updates(self):
        """Revisa mensajes nuevos cada 3 segundos"""
        while self.running:
            try:
                url = f"{self.url_base}getUpdates"
                params = {"timeout": 3}
                if self.offset:
                    params["offset"] = self.offset
                
                resp = requests.get(url, params=params, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("ok"):
                        for update in data.get("result", []):
                            self.offset = update["update_id"] + 1
                            self._process_update(update)
            except Exception:
                # Fallo silencioso en errores de red para no saturar los logs
                pass
                
            time.sleep(3)

    def _process_update(self, update):
        """Procesa una actualización de Telegram"""
        message = update.get("message", {})
        if not message:
            return
            
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "").strip()
        
        # Solo responder al CHAT_ID autorizado
        if chat_id != self.chat_id:
            return
            
        if not text.startswith("/"):
            return
            
        command = text.split(" ")[0].lower()
        
        if command == "/status":
            self._handle_status(chat_id)
        elif command == "/positions":
            self._handle_positions(chat_id)
        elif command == "/profit":
            self._handle_profit(chat_id)
        elif command == "/risk":
            self._handle_risk(chat_id)
        elif command == "/pause":
            self._handle_pause(chat_id)
        elif command == "/resume":
            self._handle_resume(chat_id)
        elif command == "/flat":
            self._handle_flat(chat_id)
        elif command == "/ask":
            self._handle_ask(chat_id, text)
        elif command == "/report":
            self._handle_report(chat_id)
        elif command == "/doctor":
            self._handle_doctor(chat_id)
        elif command in ["/help", "/start"]:
            self._handle_help(chat_id)
        else:
            self._send_message(chat_id, "❌ *Comando no reconocido.*\nUsa /help para ver la lista de comandos.")

    def _send_message(self, chat_id, text):
        """Envía respuesta a Telegram en formato Markdown"""
        url = f"{self.url_base}sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            self.logger.error(f"Error enviando comando Telegram: {e}")

    def _handle_status(self, chat_id):
        """Comando /status - Estado general"""
        acc = self.bot.connector.get_account_info()
        balance = acc["balance"] if acc else 0.0
        equity = acc["equity"] if acc else 0.0
        open_profit = acc["profit"] if acc else 0.0
        
        profit_emoji = "🟢" if open_profit >= 0 else "🔴"
        open_profit_sign = "+" if open_profit >= 0 else ""
        
        positions = self.bot.position_manager.get_open_positions()
        
        uptime_str = "N/A"
        if hasattr(self.bot.telegram, "_start_time"):
            delta = datetime.now() - self.bot.telegram._start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{hours}h {minutes}m"
            
        msg = (
            f"📊 *ESTADO DEL BOT*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Balance: `${balance:,.2f}`\n"
            f"💼 Equity: `${equity:,.2f}`\n"
            f"{profit_emoji} P&L Abierto: `{open_profit_sign}${open_profit:,.2f}`\n"
            f"📈 Posiciones Activas: `{len(positions)}`\n"
            f"⏱ Uptime: `{uptime_str}`\n"
            f"🕐 Hora local: `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        self._send_message(chat_id, msg)

    def _handle_positions(self, chat_id):
        """Comando /positions - Lista detallada de posiciones"""
        positions = self.bot.position_manager.get_open_positions()
        
        if not positions:
            self._send_message(chat_id, "😴 *No hay posiciones abiertas*")
            return
            
        msg = f"📈 *POSICIONES ABIERTAS ({len(positions)})*\n━━━━━━━━━━━━━━━━━━━━\n"
        
        for p in positions:
            direction = "BUY 🟢" if p.type == mt5.ORDER_TYPE_BUY else "SELL 🔴"
            profit = p.profit
            p_emoji = "🟢" if profit >= 0 else "🔴"
            profit_sign = "+" if profit >= 0 else ""
            
            msg += (
                f"*{p.symbol}* | {direction}\n"
                f"📦 Lotes: `{p.volume}`\n"
                f"💵 Entrada: `{p.price_open}`\n"
                f"🛑 SL: `{p.sl}` | 🎯 TP: `{p.tp}`\n"
                f"{p_emoji} P&L: `{profit_sign}${profit:,.2f}`\n\n"
            )
            
        msg += "━━━━━━━━━━━━━━━━━━━━"
        self._send_message(chat_id, msg)

    def _handle_profit(self, chat_id):
        """Comando /profit - Resumen de ganancias"""
        initial = self.bot.risk_manager.balance_inicial
        acc = self.bot.connector.get_account_info()
        balance = acc["balance"] if acc else 0.0
        open_profit = acc["profit"] if acc else 0.0
        
        diff = balance - initial
        growth_pct = (diff / initial) * 100 if initial > 0 else 0
        
        sign = "+" if diff >= 0 else ""
        emoji = "📈" if diff >= 0 else "📉"
        open_profit_emoji = "🌊" if open_profit >= 0 else "⚠️"
        open_profit_sign = "+" if open_profit >= 0 else ""
        
        msg = (
            f"💸 *RESUMEN DE GANANCIAS*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏦 Presupuesto Inicial: `${initial:,.2f}`\n"
            f"💰 Balance Actual: `${balance:,.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{emoji} Crecimiento: `{sign}${diff:,.2f}` (`{sign}{growth_pct:,.2f}%`)\n"
            f"{open_profit_emoji} P&L Flotante: `{open_profit_sign}${open_profit:,.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        self._send_message(chat_id, msg)

    def _handle_risk(self, chat_id):
        """Comando /risk - Estado de drawdown"""
        daily_dd_loss = self.bot.risk_manager.check_daily_drawdown()["loss"]
        overall_dd_loss = self.bot.risk_manager.check_overall_drawdown()["loss"]
        
        daily_limit = ChallengeConfig.MAX_DAILY_DRAWDOWN
        overall_limit = ChallengeConfig.MAX_OVERALL_DRAWDOWN
        
        daily_pct = (daily_dd_loss / daily_limit * 100) if daily_limit > 0 else 0
        overall_pct = (overall_dd_loss / overall_limit * 100) if overall_limit > 0 else 0
        
        def get_risk_level_info(pct):
            if pct < 40: return "SEGURO 🟢"
            if pct < 70: return "PRECAUCIÓN 🟡"
            if pct < 85: return "ALERTA 🟠"
            return "PELIGRO 🔴"
            
        def build_bars(pct):
            filled = min(int(pct / 10), 10)
            return ("🟥" * filled) + ("⬜" * max(10 - filled, 0))

        daily_status = get_risk_level_info(daily_pct)
        overall_status = get_risk_level_info(overall_pct)
        
        msg = (
            f"🛡️ *ESTADO DE RIESGO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 *DRAWDOWN DIARIO*\n"
            f"Nivel: *{daily_status}*\n"
            f"Pérdida actual: `${daily_dd_loss:,.2f}` / `${daily_limit:,.2f}`\n"
            f"Barra: {build_bars(daily_pct)} `{daily_pct:.1f}%`\n\n"
            f"🌍 *DRAWDOWN OVERALL*\n"
            f"Nivel: *{overall_status}*\n"
            f"Pérdida actual: `${overall_dd_loss:,.2f}` / `${overall_limit:,.2f}`\n"
            f"Barra: {build_bars(overall_pct)} `{overall_pct:.1f}%`\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        self._send_message(chat_id, msg)

    def _handle_help(self, chat_id):
        """Comando /help - Menú de comandos"""
        msg = (
            f"🤖 *CONTROL REMOTO TX3 PRO*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📡 /status - Estado general y métricas\n"
            f"📈 /positions - Detalle de posiciones abiertas\n"
            f"💸 /profit - Resumen de ganancias\n"
            f"🛡️ /risk - Estado de Drawdown y riesgo\n"
            f"🧠 /ask <pregunta> - Consulta directa al Oráculo AI\n"
            f"📝 /report - Reporte de Inteligencia Artificial\n"
            f"⏸️ /pause - Pausa el bot temporalmente\n"
            f"▶️ /resume - Reanuda la operativa\n"
            f"🧹 /flat - Cierra todas las posiciones abiertas\n"
            f"ℹ️ /help - Muestra este menú\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        self._send_message(chat_id, msg)

    def _handle_pause(self, chat_id):
        """Comando /pause - Pausa operativas"""
        self.bot.is_paused = True
        self._send_message(chat_id, "⏸️ *BOT PAUSADO*\nEl sistema no abrirá nuevas posiciones hasta usar /resume.")

    def _handle_resume(self, chat_id):
        """Comando /resume - Reanuda operativas"""
        self.bot.is_paused = False
        self._send_message(chat_id, "▶️ *BOT REANUDADO*\nSistema activo escaneando oportunidades.")

    def _handle_flat(self, chat_id):
        """Comando /flat - Cierra emergencia todo"""
        try:
            self.bot.risk_manager.emergency_close_all()
            self._send_message(chat_id, "🧹 *POSICIONES CERRADAS*\nTodas las operaciones activas han sido liquidadas manualmente.")
        except Exception as e:
            self._send_message(chat_id, f"❌ Error cerrando posiciones: `{str(e)}`")

    def _handle_ask(self, chat_id, text):
        """Comando /ask - Consulta directa al Oráculo AI (Gemini)"""
        parts = text.split(" ", 1)
        if len(parts) < 2:
            self._send_message(chat_id, "⚠️ ¡Debes formular una pregunta!\nEjemplo: `/ask Cómo ves el mercado hoy?`")
            return
            
        question = parts[1]
        self._send_message(chat_id, "💬 *Oráculo Pensando...*")
        
        def ask_ai():
            answer = self.bot.oracle.ask_oracle(question)
            self._send_message(chat_id, f"👁️‍🗨️ *ORÁCULO AI:*\n\n{answer}")
            
        threading.Thread(target=ask_ai, daemon=True).start()

    def _handle_report(self, chat_id):
        """Comando /report - Informe AI de situación"""
        self._send_message(chat_id, "📝 *Generando Reporte de Inteligencia Artificial...*")
        
        def generate_report():
            acc = self.bot.connector.get_account_info()
            daily_dd = self.bot.risk_manager.check_daily_drawdown()["loss"]
            daily_limit = ChallengeConfig.MAX_DAILY_DRAWDOWN
            overall_dd = self.bot.risk_manager.check_overall_drawdown()["loss"]
            positions = len(self.bot.position_manager.get_open_positions())
            
            context = (
                f"Tengo {positions} posiciones abiertas. "
                f"Mi Equidad es ${acc['equity'] if acc else 0}. "
                f"Dibujo Diario (Pérdida de hoy) es ${daily_dd} (Límite ${daily_limit}). "
                f"Pérdida Total es ${overall_dd}. "
                f"Dame 2 párrafos: 1 resumiendo audazmente el estado, y 1 dándome un consejo directivo como mi CIO."
            )
            answer = self.bot.oracle.ask_oracle(context)
            self._send_message(chat_id, f"📊 *REPORTE INSTITUCIONAL (AI):*\n\n{answer}")
            
        threading.Thread(target=generate_report, daemon=True).start()

    def _handle_doctor(self, chat_id):
        """Comando /doctor - Diagnóstico Médico AI del sistema"""
        self._send_message(chat_id, "🩺 *Dr. Quant revisando signos vitales del sistema...*")
        
        def run_diagnosis():
            acc = self.bot.connector.get_account_info()
            uptime_str = "Desconocido"
            if hasattr(self, "_start_time"):
                delta = datetime.now() - self._start_time
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                uptime_str = f"{hours}h {minutes}m"
                
            # Calcular horas desde último trade
            hours_since_last = "Desconocido (> 7 días o Error)"
            try:
                now = datetime.now()
                back = now - timedelta(days=7)
                deals = mt5.history_deals_get(back, now)
                if deals and len(deals) > 0:
                    last_deal_time = datetime.fromtimestamp(deals[-1].time)
                    hours_diff = (now - last_deal_time).total_seconds() / 3600
                    hours_since_last = f"{hours_diff:.1f}"
            except Exception:
                pass

            metrics = {
                "uptime": uptime_str,
                "hours_since_last_trade": hours_since_last,
                "daily_dd": self.bot.risk_manager.check_daily_drawdown()["loss"],
                "overall_dd": self.bot.risk_manager.check_overall_drawdown()["loss"],
                "mt5_connected": self.bot.connector.is_connected(),
                "recent_errors": "Revisar logs en caso de silencio"
            }
            
            diagnosis = self.bot.oracle.evaluate_system_health(metrics)
            self._send_message(chat_id, f"👨‍⚕️ *DIAGNÓSTICO DR. QUANT:*\n\n{diagnosis}")
            
        threading.Thread(target=run_diagnosis, daemon=True).start()
