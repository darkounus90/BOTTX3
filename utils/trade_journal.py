"""
📓 Trade Journal - Registro Detallado de Trades
=================================================
Registra cada trade en CSV para análisis posterior.
Incluye toda la información relevante para auditoría.
"""

import csv
import json
import os
import MetaTrader5 as mt5
import time as time_module
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict
from config.settings import BotConfig
from utils.logger import BotLogger

# Zona horaria estándar para TODOS los timestamps del bot
_ET = ZoneInfo(BotConfig.TIMEZONE)


class TradeJournal:
    """
    Registra todos los trades en CSV y JSON detallado.

    CSV: resumen rápido para Excel/Google Sheets
    JSON: detalle completo para análisis programático
    """

    CSV_HEADERS = [
        "timestamp",
        "trade_id",
        "action",           # OPEN / CLOSE
        "type",             # BUY / SELL
        "symbol",
        "volume",
        "price",
        "sl",
        "tp",
        "sl_pips",
        "tp_pips",
        "rr_ratio",
        "profit",
        "profit_pips",
        "balance_after",
        "equity_after",
        "daily_dd_used",
        "overall_dd_used",
        "session",
        "strategy",
        "reason",
        "duration",
        "phase",
        "comment",
    ]

    def __init__(self, logger: BotLogger, phase: int):
        self.logger = logger
        self.phase = phase

        # Crear directorios
        self.csv_path = BotConfig.JOURNAL_FILE
        self.detail_dir = BotConfig.JOURNAL_DETAILED_DIR
        
        # AGREGAR DEPURAción: ¿Dónde está guardando realmente?
        abs_csv = os.path.abspath(self.csv_path)
        self.logger.info(f"🕵️ RUTA DEL JOURNAL: {abs_csv}")

        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        os.makedirs(self.detail_dir, exist_ok=True)

        # Inicializar CSV si no existe
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
            self.logger.info(f"📓 Trade Journal creado: {self.csv_path}")
        else:
            # Validar si el header tiene 'action' (v4 compatibility)
            try:
                with open(self.csv_path, "r", encoding="utf-8") as f:
                    header = f.readline().strip()
                    if "action" not in header:
                        self.logger.warning("📓 Journal CSV desactualizado (falta columna 'action'). Recreando...")
                        f.close()
                        os.rename(self.csv_path, self.csv_path + ".old")
                        with open(self.csv_path, "w", newline="", encoding="utf-8") as nf:
                            writer = csv.writer(nf)
                            writer.writerow(self.CSV_HEADERS)
                    else:
                        self.logger.info(f"📓 Trade Journal existente: {self.csv_path}")
            except Exception:
                self.logger.info(f"📓 Trade Journal existente: {self.csv_path}")

        self.trade_count = self._get_trade_count()
        self._broker_offset = None  # Offset dinámico detectado entre MT5 y UTC

    def _get_trade_count(self) -> int:
        """Cuenta el número de trades registrados"""
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                return sum(1 for _ in f) - 1  # Restar header
        except Exception:
            return 0

    def _next_trade_id(self) -> str:
        """Genera un ID único para el trade"""
        self.trade_count += 1
        return f"TX3-P{self.phase}-{self.trade_count:04d}"

    def record_open(
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
        balance: float,
        equity: float,
        daily_dd: float,
        overall_dd: float,
        session: str,
        strategy: str,
        reason: str,
    ) -> str:
        """
        Registra la apertura de un trade.

        Returns:
            trade_id para referencia futura
        """
        trade_id = self._next_trade_id()
        now = datetime.now(_ET)

        row = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_id": trade_id,
            "action": "OPEN",
            "type": order_type,
            "symbol": symbol,
            "volume": volume,
            "price": price,
            "sl": sl,
            "tp": tp,
            "sl_pips": sl_pips,
            "tp_pips": tp_pips,
            "rr_ratio": rr_ratio,
            "profit": 0,
            "profit_pips": 0,
            "balance_after": balance,
            "equity_after": equity,
            "daily_dd_used": daily_dd,
            "overall_dd_used": overall_dd,
            "session": session,
            "strategy": strategy,
            "reason": reason,
            "duration": "",
            "phase": self.phase,
            "comment": "",
        }

        self._write_csv_row(row)
        self._write_json_detail(trade_id, "open", row)

        self.logger.info(f"📓 Trade registrado: {trade_id} ({order_type} {symbol})")
        return trade_id

    def record_close(
        self,
        trade_id: str,
        symbol: str,
        order_type: str,
        volume: float,
        close_price: float,
        profit: float,
        profit_pips: float,
        balance: float,
        equity: float,
        daily_dd: float,
        overall_dd: float,
        duration: str,
        close_reason: str = "",
    ):
        """Registra el cierre de un trade"""
        now = datetime.now(_ET)

        row = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "trade_id": trade_id,
            "action": "CLOSE",
            "type": order_type,
            "symbol": symbol,
            "volume": volume,
            "price": close_price,
            "sl": "",
            "tp": "",
            "sl_pips": "",
            "tp_pips": "",
            "rr_ratio": "",
            "profit": profit,
            "profit_pips": profit_pips,
            "balance_after": balance,
            "equity_after": equity,
            "daily_dd_used": daily_dd,
            "overall_dd_used": overall_dd,
            "session": "",
            "strategy": "",
            "reason": close_reason,
            "duration": duration,
            "phase": self.phase,
            "comment": "",
        }

        self._write_csv_row(row)
        self._write_json_detail(trade_id, "close", row)

        emoji = "✅" if profit >= 0 else "❌"
        self.logger.info(
            f"📓 {emoji} Trade cerrado: {trade_id} | "
            f"P&L: ${profit:+,.2f} ({profit_pips:+.1f} pips)"
        )

    def _write_csv_row(self, data: dict):
        """Escribe una fila al CSV"""
        try:
            with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.CSV_HEADERS)
                writer.writerow(data)
        except Exception as e:
            self.logger.error(f"Error escribiendo al journal CSV: {e}")

    def _write_json_detail(self, trade_id: str, action: str, data: dict):
        """Escribe un archivo JSON detallado por trade"""
        try:
            filename = f"{trade_id}_{action}.json"
            filepath = os.path.join(self.detail_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            self.logger.error(f"Error escribiendo JSON detallado: {e}")

    def get_today_stats(self) -> dict:
        """Obtiene las estadísticas del día (hora ET)"""
        today = datetime.now(_ET).strftime("%Y-%m-%d")
        trades = []
        wins = 0
        losses = 0
        total_profit = 0.0

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row.get("timestamp") or not row.get("action"):
                        continue
                    if row["timestamp"].startswith(today) and row["action"] == "CLOSE":
                        trades.append(row)
                        profit = float(row.get("profit", 0))
                        total_profit += profit
                        if profit >= 0:
                            wins += 1
                        else:
                            losses += 1
        except Exception:
            pass

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0

        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": total_profit,
        }

    def get_all_stats(self) -> dict:
        """Obtiene las estadísticas totales"""
        wins = 0
        losses = 0
        total_profit = 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        largest_win = 0.0
        largest_loss = 0.0

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["action"] == "CLOSE":
                        profit = float(row.get("profit", 0))
                        total_profit += profit
                        if profit >= 0:
                            wins += 1
                            gross_profit += profit
                            largest_win = max(largest_win, profit)
                        else:
                            losses += 1
                            gross_loss += abs(profit)
                            largest_loss = min(largest_loss, profit)
        except Exception:
            pass

        total = wins + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        avg_win = (gross_profit / wins) if wins > 0 else 0
        avg_loss = (gross_loss / losses) if losses > 0 else 0
        expectancy = ((win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss))

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
        }
    def get_recent_trades(self, limit: int = 15) -> list:
        """Obtiene los últimos N trades, agrupándolos por Position ID para que el
        dashboard no muestre los cierres parciales de forma fragmentada."""
        trades = []
        try:
            if not os.path.exists(self.csv_path):
                return []
                
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
                
                pid_map = {}
                
                # Buscamos los cierres (CLOSE) de atrás hacia adelante
                for row in reversed(all_rows):
                    if row.get("action") == "CLOSE":
                        pid = None
                        m = re.search(r'Pos #(\d+)', row.get('comment', ''))
                        if not m:
                            m = re.search(r'Pos #(\d+)', row.get('reason', ''))
                        if m:
                            pid = m.group(1)
                        else:
                            m = re.search(r'TRADE-(\d+)', row.get('trade_id', ''))
                            if m:
                                pid = m.group(1)
                            else:
                                pid = row.get('trade_id') # Fallback al id completo

                        if pid in pid_map:
                            # Sumar lotaje y profit al registro existente en memoria
                            existing = pid_map[pid]
                            existing['profit'] += float(row.get("profit") or 0.0)
                            existing['volume'] += float(row.get("volume") or 0.0)
                        else:
                            if len(trades) >= limit:
                                continue # Ya llenamos el dashboard, pero seguimos iterando por si existen parciales más viejos
                                
                            # Si es la primera vez que lo vemos (el más reciente), lo guardamos
                            trade = {
                                "trade_id": row.get("trade_id", ""),
                                "timestamp": row.get("timestamp", ""),
                                "symbol": row.get("symbol", ""),
                                "type": row.get("type", ""),
                                "volume": float(row.get("volume") or 0.0),
                                "profit": float(row.get("profit") or 0.0),
                                "profit_pips": float(row.get("profit_pips") or 0.0),
                                "duration": row.get("duration", ""),
                                "strategy": row.get("strategy", ""),
                                "reason": row.get("reason", ""),
                                "comment": row.get("comment", "")
                            }
                            pid_map[pid] = trade
                            trades.append(trade)

                # Formatear la salida matemática
                for t in trades:
                    t["volume"] = str(round(t["volume"], 2))
                    t["profit"] = round(t["profit"], 2)

        except Exception as e:
            self.logger.error(f"Error leyendo trades recientes: {e}")
            
        return trades
    def sync_mt5_history(self, deals) -> list:
        """
        Sincroniza los trades cerrados externamente (MT5 app, TP/SL, etc.)
        directamente al journal, evitando depender de la memoria de Python.
        
        Args:
            deals: Tupla de deals desde mt5.history_deals_get()
            
        Returns:
            list: Lista de diccionarios con la información de los trades nuevos sincronizados.
        """
        if not deals:
            return []
            
        newly_synced = []
        existing_signatures = set()
        
        # ─── DETECTAR OFFSET DEL BROKER DINÁMICAMENTE ───
        if self._broker_offset is None:
            try:
                # Intentamos obtener el tick de un par mayor para ver la hora del servidor
                tick = mt5.symbol_info_tick("EURUSD")
                if tick:
                    server_time = tick.time
                    utc_now = int(time_module.time())
                    # Offset en segundos (Ej: GMT+2 = +7200)
                    self._broker_offset = server_time - utc_now
                    self.logger.info(f"🕒 Broker Offset detectado: {self._broker_offset}s (GMT {self._broker_offset/3600:+.1f})")
            except Exception as e:
                self.logger.warning(f"No se pudo detectar offset del broker: {e}")
                self._broker_offset = 0  # Fallback a asuncion de UTC
            
        newly_synced = []
        existing_signatures = set()
        existing_fuzzy_trades = []
        
        # Cargar firmas existentes para evitar duplicados
        try:
            if os.path.exists(self.csv_path):
                with open(self.csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # 1. Firma por Ticket Exacto (si existe)
                        comment = row.get("comment", "")
                        if "Deal #" in comment or "Pos #" in comment:
                            existing_signatures.add(comment)
                        
                        # 2. Firma Temporal Robusta para transacciones que no guardaron ticket
                        try:
                            p = round(float(row.get("profit") or 0.0), 2)
                            ts_str = row.get("timestamp", "")
                            
                            # Validar que si tiene longitud correcta antes de pasarlo al datetime
                            if len(ts_str) >= 19:
                                ts_dt = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
                                # Hacemos aware al datetime si la fecha no tiene TZ info
                                ts_dt = ts_dt.replace(tzinfo=_ET)
                            else:
                                continue

                            existing_fuzzy_trades.append({
                                "profit": p,
                                "symbol": row.get("symbol", ""),
                                "time": ts_dt
                            })
                        except Exception as e:
                            pass
        except Exception as e:
            self.logger.error(f"Error cargando firmas para sync: {e}")

        # Recorremos cada DEAL de cierre sin agrupar, para soportar Cierres Parciales perfectamente
        for deal in deals:
            # Solo queremos los cierres (donde está el profit real)
            # entry=1 (OUT), entry=2 (INOUT), entry=3 (OUT_BY)
            if deal.entry not in [1, 2, 3]: 
                continue
                
            # Convertir timestamp del broker a UTC real y luego a nuestra ET
            utc_timestamp = deal.time - (self._broker_offset or 0)
            dt = datetime.fromtimestamp(utc_timestamp, tz=_ET)
            ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            # Profit Neto = Beneficio Bruto + Comisión + Swap
            profit = round(float(deal.profit + deal.commission + deal.swap), 2)
            symbol = deal.symbol
            
            # Signature robusta: Ticket del Deal (infalible)
            comment_sig = f"Deal #{deal.ticket}"
            
            # Verificamos si el ticket ya existe
            if comment_sig in existing_signatures:
                continue
                
            # 🛡️ SINCRONIZACIÓN FORZADA POR TICKET
            # Eliminamos la búsqueda por profit/tiempo (fuzzy) para asegurar que 
            # cada operación manual se registre sin excepciones.
            if True:
                # No está en el journal, lo agregamos como un trade independiente (o parcial)
                trade_id = f"SYNC-{deal.ticket}"
                
                # INVERTIR LA DIRECCIÓN: Un deal de cierre de tipo SELL(1) significa que la posición original era BUY.
                # Un deal de cierre de tipo BUY(0) significa que la posición original era SELL.
                pos_direction = "SELL" if deal.type == 0 else "BUY"
                
                # Calcular pips aproximados (en deals de cierre, mt5 no da pips directo fácilmente)
                profit_pips = 0.0
                
                row = {
                    "timestamp": ts,
                    "trade_id": trade_id,
                    "action": "CLOSE", 
                    "type": pos_direction,
                    "symbol": symbol,
                    "volume": round(float(deal.volume), 2),
                    "price": deal.price,
                    "sl": "",
                    "tp": "",
                    "sl_pips": "",
                    "tp_pips": "",
                    "rr_ratio": "",
                    "profit": profit,
                    "profit_pips": profit_pips,
                    "balance_after": 0,
                    "equity_after": 0,
                    "daily_dd_used": 0,
                    "overall_dd_used": 0,
                    "session": "N/A",
                    "strategy": "MT5_SYNC",
                    "reason": f"Sincronizado (Pos #{deal.position_id})",
                    "duration": "N/A",
                    "phase": self.phase,
                    "comment": comment_sig,
                }
                
                self._write_csv_row(row)
                existing_signatures.add(comment_sig)
                newly_synced.append(row)
                
        sync_count = len(newly_synced)
        if sync_count > 0:
            self.logger.success(f"📓 Sincronizadas {sync_count} posiciones externas al journal.")
            
        return newly_synced
