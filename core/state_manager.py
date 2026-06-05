import sqlite3
import json
import os
from datetime import datetime
from typing import Any, Optional

class StateManager:
    """
    Gestor de persistencia ligera usando SQLite.
    Almacena variables clave (Drawdown, Balance Inicial, Fases)
    para que sobrevivan a reinicios del bot.
    """
    
    def __init__(self, db_path: str = "data/bot_state.db"):
        self.db_path = db_path
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            """)
            conn.commit()

    def set_value(self, key: str, value: Any):
        """Guarda un valor (serializado a JSON) en la base de datos."""
        serialized_val = json.dumps(value)
        now = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_state (key, value, updated_at) 
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET 
                    value=excluded.value,
                    updated_at=excluded.updated_at
            """, (key, serialized_val, now))
            conn.commit()

    def get_value(self, key: str, default: Any = None) -> Any:
        """Recupera un valor de la base de datos. Retorna `default` si no existe."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM bot_state WHERE key=?", (key,))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            
            return default
