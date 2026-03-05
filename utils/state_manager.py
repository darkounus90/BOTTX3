"""
💾 State Manager - Persistencia del Estado del Bot
====================================================
Guarda y restaura el estado del bot entre reinicios.
Nunca pierdas el tracking de días rentables o drawdown.
"""

import json
import os
from datetime import datetime
from config.settings import BotConfig
from utils.logger import BotLogger


class StateManager:
    """
    Persiste el estado del bot a disco en formato JSON.
    Permite reanudar el bot sin perder información.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.state_file = BotConfig.STATE_FILE

        # Crear directorio
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

    def save_state(self, state: dict):
        """
        Guarda el estado actual del bot.

        Args:
            state: diccionario con el estado completo
        """
        state["_last_saved"] = datetime.now().isoformat()
        state["_version"] = "1.0"

        try:
            # Escribir a archivo temporal primero (atómico)
            tmp_file = self.state_file + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False, default=str)

            # Renombrar (atómico en la mayoría de sistemas)
            os.replace(tmp_file, self.state_file)
            self.logger.debug(f"💾 Estado guardado en background")

        except Exception as e:
            self.logger.error(f"Error guardando estado: {e}")

    def load_state(self) -> dict | None:
        """
        Carga el estado guardado.

        Returns:
            dict con el estado, o None si no existe
        """
        if not os.path.exists(self.state_file):
            self.logger.info("💾 No hay estado guardado previo")
            return None

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            last_saved = state.get("_last_saved", "desconocido")
            self.logger.success(f"💾 Estado restaurado (guardado: {last_saved})")

            return state

        except json.JSONDecodeError as e:
            self.logger.error(f"Error parseando estado: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error cargando estado: {e}")
            return None

    def build_state(
        self,
        phase: int,
        balance_inicial: float,
        equity_inicio_dia: float,
        profitable_days: int,
        daily_profits: list,
        total_trading_days: int,
        trades_today: int,
        highest_balance: float,
        is_daily_warning: bool,
        is_overall_warning: bool,
    ) -> dict:
        """Construye el diccionario de estado"""
        return {
            "phase": phase,
            "balance_inicial": balance_inicial,
            "equity_inicio_dia": equity_inicio_dia,
            "profitable_days": profitable_days,
            "daily_profits": daily_profits,
            "total_trading_days": total_trading_days,
            "trades_today": trades_today,
            "highest_balance": highest_balance,
            "is_daily_warning": is_daily_warning,
            "is_overall_warning": is_overall_warning,
        }

    def has_saved_state(self) -> bool:
        """Verifica si hay un estado guardado"""
        return os.path.exists(self.state_file)

    def delete_state(self):
        """Elimina el estado guardado"""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
            self.logger.info("💾 Estado eliminado")
