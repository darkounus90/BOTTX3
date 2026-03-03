"""
📓 Trade Journal - Registro Detallado de Trades
=================================================
Registra cada trade en CSV para análisis posterior.
Incluye toda la información relevante para auditoría.
"""

import csv
import json
import os
from datetime import datetime
from config.settings import BotConfig
from utils.logger import BotLogger


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
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        os.makedirs(self.detail_dir, exist_ok=True)

        # Inicializar CSV si no existe
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
            self.logger.info(f"📓 Trade Journal creado: {self.csv_path}")
        else:
            self.logger.info(f"📓 Trade Journal existente: {self.csv_path}")

        self.trade_count = self._get_trade_count()

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
        now = datetime.now()

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
        now = datetime.now()

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
        """Obtiene las estadísticas del día"""
        today = datetime.now().strftime("%Y-%m-%d")
        trades = []
        wins = 0
        losses = 0
        total_profit = 0.0

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
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
    def get_recent_trades(self, limit: int = 20) -> list:
        """Obtiene los últimos N trades cerrados para el dashboard"""
        trades = []
        try:
            if not os.path.exists(self.csv_path):
                return []
                
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_rows = list(reader)
                
                # Buscamos los cierres (CLOSE) de atrás hacia adelante
                for row in reversed(all_rows):
                    if row["action"] == "CLOSE":
                        # Limpiar datos para el frontend
                        trade = {
                            "timestamp": row.get("timestamp", ""),
                            "symbol": row.get("symbol", ""),
                            "type": row.get("type", ""),
                            "volume": row.get("volume", "0.00"),
                            "profit": float(row.get("profit", 0)),
                            "profit_pips": float(row.get("profit_pips", 0)),
                            "duration": row.get("duration", ""),
                            "strategy": row.get("strategy", ""),
                            "reason": row.get("reason", "")
                        }
                        trades.append(trade)
                    
                    if len(trades) >= limit:
                        break
        except Exception as e:
            self.logger.error(f"Error leyendo trades recientes: {e}")
            
        return trades
    def sync_mt5_history(self, deals: tuple):
        """
        Sincroniza el historial de MT5 con el Journal.
        Evita duplicados escaneando el profit y timestamp único.
        """
        if not deals:
            return 0
            
        sync_count = 0
        existing_signatures = set()
        
        # Cargar firmas existentes para evitar duplicados
        try:
            if os.path.exists(self.csv_path):
                with open(self.csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Una firma única: timestamp + profit (redondeado) + symbol
                        try:
                            p = round(float(row.get("profit", "0")), 2)
                            sig = f"{row.get('timestamp')}_{p}_{row.get('symbol')}"
                            existing_signatures.add(sig)
                        except: pass
        except Exception as e:
            self.logger.error(f"Error cargando firmas para sync: {e}")

        for deal in deals:
            # Solo queremos los cierres (donde está el profit real)
            # entry=1 (OUT), entry=2 (INOUT), entry=3 (OUT_BY)
            if deal.entry not in [1, 2, 3]: 
                continue
                
            dt = datetime.fromtimestamp(deal.time)
            ts = dt.strftime("%Y-%m-%d %H:%M:%S")
            profit = round(float(deal.profit), 2)
            symbol = deal.symbol
            
            # Signature robusta: TS + PROFIT (rounded) + SYMBOL
            sig = f"{ts}_{profit}_{symbol}"
            
            if sig not in existing_signatures:
                # No está en el journal, lo agregamos
                trade_id = f"SYNC-{deal.ticket}"
                
                row = {
                    "timestamp": ts,
                    "trade_id": trade_id,
                    "action": "CLOSE", # Lo tratamos como cierre para el dashboard
                    "type": "BUY" if deal.type == 0 else "SELL", # DEAL_TYPE_BUY = 0, SELL = 1
                    "symbol": symbol,
                    "volume": deal.volume,
                    "price": deal.price,
                    "sl": "",
                    "tp": "",
                    "sl_pips": "",
                    "tp_pips": "",
                    "rr_ratio": "",
                    "profit": profit,
                    "profit_pips": 0, # Difícil calcular pips sin el open price exacto aquí
                    "balance_after": 0, # Desconocido del deal directo
                    "equity_after": 0,
                    "daily_dd_used": 0,
                    "overall_dd_used": 0,
                    "session": "N/A",
                    "strategy": "EXTERNAL/MANUAL",
                    "reason": "Sincronizado desde MT5",
                    "duration": "N/A",
                    "phase": self.phase,
                    "comment": f"Deal #{deal.deal}",
                }
                
                self._write_csv_row(row)
                existing_signatures.add(sig)
                sync_count += 1
                
        if sync_count > 0:
            self.logger.success(f"📓 Sincronizados {sync_count} trades externos al journal.")
            
        return sync_count
