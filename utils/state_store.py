"""
💾 StateStore - Capa de Persistencia SQLite para BOTTX3
=========================================================
Una sola base de datos (data/bot_state.db) con dos tablas:
  - risk_state   → equity_inicio_dia, flags de drawdown, balance_inicial dinámico
  - phase_state  → profitable_days, daily_profits, total_trading_days

Diseño:
  - Cada tabla tiene UNA sola fila identificada por (phase, trading_day).
  - "trading_day" es la fecha en la zona horaria de Praga (reset FTMO a medianoche).
  - Al arrancar, cada módulo llama a .load() y recupera su estado exacto.
  - Al cambiar cualquier valor relevante, llama a .save() — es O(1), no importa la frecuencia.
  - La tabla de auditoría (audit_log) guarda cada cambio de estado con timestamp
    para poder reconstruir el histórico si algo falla.

Uso rápido:
    from utils.state_store import StateStore
    store = StateStore()
    store.save_risk(equity_inicio_dia=50000.0, is_daily_warning=False, ...)
    data = store.load_risk()
"""

import sqlite3
import json
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from typing import Optional


# ─── Zona horaria FTMO (Praga) para calcular el "día" ────────────────────────
def _ftmo_today() -> str:
    """Retorna la fecha actual en la zona horaria de Praga como string YYYY-MM-DD."""
    try:
        now = datetime.now(ZoneInfo("Europe/Prague"))
    except Exception:
        # Fallback para Windows sin tzdata instalado
        now = datetime.now(timezone.utc) + timedelta(hours=1)
    return now.strftime("%Y-%m-%d")


DB_PATH = os.path.join("data", "bot_state.db")


class StateStore:
    """
    Interfaz de persistencia SQLite para RiskManager y PhaseTracker.
    Thread-safe: usa una conexión por llamada (check_same_thread=False con WAL).
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    # ──────────────────────────────────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # WAL mode: lecturas y escrituras no se bloquean mutuamente
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        """Crea las tablas si no existen. Idempotente."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS risk_state (
                    trading_day        TEXT    NOT NULL,   -- 'YYYY-MM-DD' en zona Praga
                    equity_inicio_dia  REAL    NOT NULL,   -- equity al inicio del día (reset 5PM EST)
                    balance_inicial    REAL    NOT NULL,   -- puede subir por Fortaleza Matemática
                    is_daily_warning   INTEGER NOT NULL DEFAULT 0,
                    is_daily_emergency INTEGER NOT NULL DEFAULT 0,
                    is_overall_warning INTEGER NOT NULL DEFAULT 0,
                    is_overall_emergency INTEGER NOT NULL DEFAULT 0,
                    updated_at         TEXT    NOT NULL,   -- ISO8601 UTC
                    PRIMARY KEY (trading_day)
                );

                CREATE TABLE IF NOT EXISTS phase_state (
                    phase              INTEGER NOT NULL,
                    trading_day        TEXT    NOT NULL,   -- 'YYYY-MM-DD' en zona Praga
                    profitable_days    INTEGER NOT NULL DEFAULT 0,
                    total_trading_days INTEGER NOT NULL DEFAULT 0,
                    daily_profits_json TEXT    NOT NULL DEFAULT '[]',  -- lista JSON de floats
                    current_day_profit REAL    NOT NULL DEFAULT 0.0,
                    updated_at         TEXT    NOT NULL,
                    PRIMARY KEY (phase, trading_day)
                );

                -- Auditoría: cada cambio queda registrado.
                -- Útil para depurar reinicios inesperados.
                CREATE TABLE IF NOT EXISTS audit_log (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         TEXT    NOT NULL,
                    table_name TEXT    NOT NULL,
                    event      TEXT    NOT NULL,
                    payload    TEXT    NOT NULL
                );
            """)

    # ──────────────────────────────────────────────────────────────────────────
    # RISK STATE
    # ──────────────────────────────────────────────────────────────────────────

    def save_risk(
        self,
        equity_inicio_dia: float,
        balance_inicial: float,
        is_daily_warning: bool = False,
        is_daily_emergency: bool = False,
        is_overall_warning: bool = False,
        is_overall_emergency: bool = False,
        trading_day: Optional[str] = None,
    ):
        """Persiste el estado del RiskManager para el día actual."""
        day = trading_day or _ftmo_today()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO risk_state
                    (trading_day, equity_inicio_dia, balance_inicial,
                     is_daily_warning, is_daily_emergency,
                     is_overall_warning, is_overall_emergency, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trading_day) DO UPDATE SET
                    equity_inicio_dia   = excluded.equity_inicio_dia,
                    balance_inicial     = excluded.balance_inicial,
                    is_daily_warning    = excluded.is_daily_warning,
                    is_daily_emergency  = excluded.is_daily_emergency,
                    is_overall_warning  = excluded.is_overall_warning,
                    is_overall_emergency= excluded.is_overall_emergency,
                    updated_at          = excluded.updated_at
            """, (
                day,
                equity_inicio_dia,
                balance_inicial,
                int(is_daily_warning),
                int(is_daily_emergency),
                int(is_overall_warning),
                int(is_overall_emergency),
                now_iso,
            ))

            # Auditoría
            conn.execute(
                "INSERT INTO audit_log (ts, table_name, event, payload) VALUES (?,?,?,?)",
                (now_iso, "risk_state", "save", json.dumps({
                    "day": day,
                    "equity_inicio_dia": equity_inicio_dia,
                    "balance_inicial": balance_inicial,
                    "flags": {
                        "daily_warning": is_daily_warning,
                        "daily_emergency": is_daily_emergency,
                        "overall_warning": is_overall_warning,
                        "overall_emergency": is_overall_emergency,
                    }
                }))
            )

    def load_risk(self, trading_day: Optional[str] = None) -> Optional[dict]:
        """
        Carga el estado del RiskManager para el día dado.
        Retorna None si no existe registro para ese día (primera vez del día).
        """
        day = trading_day or _ftmo_today()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM risk_state WHERE trading_day = ?", (day,)
            ).fetchone()

        if row is None:
            return None

        return {
            "trading_day":           row["trading_day"],
            "equity_inicio_dia":     row["equity_inicio_dia"],
            "balance_inicial":       row["balance_inicial"],
            "is_daily_warning":      bool(row["is_daily_warning"]),
            "is_daily_emergency":    bool(row["is_daily_emergency"]),
            "is_overall_warning":    bool(row["is_overall_warning"]),
            "is_overall_emergency":  bool(row["is_overall_emergency"]),
            "updated_at":            row["updated_at"],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PHASE STATE
    # ──────────────────────────────────────────────────────────────────────────

    def save_phase(
        self,
        phase: int,
        profitable_days: int,
        total_trading_days: int,
        daily_profits: list,
        current_day_profit: float = 0.0,
        trading_day: Optional[str] = None,
    ):
        """Persiste el estado del PhaseTracker."""
        day = trading_day or _ftmo_today()
        now_iso = datetime.now(timezone.utc).isoformat()
        profits_json = json.dumps([round(p, 4) for p in daily_profits])

        with self._connect() as conn:
            conn.execute("""
                INSERT INTO phase_state
                    (phase, trading_day, profitable_days, total_trading_days,
                     daily_profits_json, current_day_profit, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phase, trading_day) DO UPDATE SET
                    profitable_days    = excluded.profitable_days,
                    total_trading_days = excluded.total_trading_days,
                    daily_profits_json = excluded.daily_profits_json,
                    current_day_profit = excluded.current_day_profit,
                    updated_at         = excluded.updated_at
            """, (
                phase, day, profitable_days, total_trading_days,
                profits_json, current_day_profit, now_iso,
            ))

            conn.execute(
                "INSERT INTO audit_log (ts, table_name, event, payload) VALUES (?,?,?,?)",
                (now_iso, "phase_state", "save", json.dumps({
                    "phase": phase,
                    "day": day,
                    "profitable_days": profitable_days,
                    "total_trading_days": total_trading_days,
                    "current_day_profit": current_day_profit,
                }))
            )

    def load_phase(self, phase: int, trading_day: Optional[str] = None) -> Optional[dict]:
        """
        Carga el estado más reciente del PhaseTracker para la fase dada.
        Si trading_day es None, busca el registro MÁS RECIENTE (no solo el de hoy),
        para recuperar el acumulado correcto de días rentables al reiniciar.
        """
        with self._connect() as conn:
            if trading_day:
                row = conn.execute(
                    "SELECT * FROM phase_state WHERE phase = ? AND trading_day = ?",
                    (phase, trading_day)
                ).fetchone()
            else:
                # Buscar el más reciente de la fase (acumulado total)
                row = conn.execute(
                    "SELECT * FROM phase_state WHERE phase = ? ORDER BY trading_day DESC LIMIT 1",
                    (phase,)
                ).fetchone()

        if row is None:
            return None

        return {
            "phase":              row["phase"],
            "trading_day":        row["trading_day"],
            "profitable_days":    row["profitable_days"],
            "total_trading_days": row["total_trading_days"],
            "daily_profits":      json.loads(row["daily_profits_json"]),
            "current_day_profit": row["current_day_profit"],
            "updated_at":         row["updated_at"],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # UTILIDADES
    # ──────────────────────────────────────────────────────────────────────────

    def get_risk_history(self, last_n_days: int = 10) -> list:
        """Retorna los últimos N registros de risk_state (útil para el dashboard)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM risk_state ORDER BY trading_day DESC LIMIT ?",
                (last_n_days,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_audit_tail(self, n: int = 50) -> list:
        """Últimas N entradas del log de auditoría."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (n,)
            ).fetchall()
        return [dict(r) for r in rows]
