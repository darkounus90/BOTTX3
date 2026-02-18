"""
📐 Base Strategy - Clase Base para Estrategias
================================================
Todas las estrategias deben heredar de esta clase
e implementar el método `generate_signal()`.
"""

from abc import ABC, abstractmethod
from utils.logger import BotLogger


class BaseStrategy(ABC):
    """
    Clase base abstracta para todas las estrategias de trading.

    Cada estrategia debe implementar:
    - generate_signal(): Genera señales de compra/venta
    - get_name(): Retorna el nombre de la estrategia
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger

    @abstractmethod
    def generate_signal(self) -> dict | None:
        """
        Genera una señal de trading.

        Returns:
            dict con:
                - signal: "BUY" o "SELL"
                - symbol: Par de divisas
                - stop_loss_pips: Distancia del SL en pips
                - take_profit_pips: Distancia del TP en pips
                - reason: Razón de la señal
            None si no hay señal
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Retorna el nombre de la estrategia"""
        pass

    def log_signal(self, signal: dict):
        """Log de una señal generada"""
        direction = "🔵 COMPRA" if signal["signal"] == "BUY" else "🔴 VENTA"
        self.logger.separator()
        self.logger.trade(f"SEÑAL DETECTADA: {direction}")
        self.logger.trade(f"  Estrategia:  {self.get_name()}")
        self.logger.trade(f"  Símbolo:     {signal['symbol']}")
        self.logger.trade(f"  SL:          {signal['stop_loss_pips']} pips")
        self.logger.trade(f"  TP:          {signal['take_profit_pips']} pips")
        self.logger.trade(f"  R:R:         1:{signal['take_profit_pips'] / signal['stop_loss_pips']:.1f}")
        self.logger.trade(f"  Razón:       {signal.get('reason', 'N/A')}")
