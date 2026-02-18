"""
🔌 Conector MetaTrader 5
=========================
Gestiona la conexión y desconexión a MetaTrader 5.
"""

import MetaTrader5 as mt5
from utils.logger import BotLogger


class MT5Connector:
    """Maneja la conexión con MetaTrader 5"""

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.connected = False

    def connect(self) -> bool:
        """
        Inicializa la conexión con MT5.
        MT5 debe estar instalado y abierto con la cuenta TX3 logueada.
        """
        self.logger.info("Conectando a MetaTrader 5...")

        if not mt5.initialize():
            error = mt5.last_error()
            self.logger.error(f"Error al inicializar MT5: {error}")
            self.logger.error(
                "Asegúrate de que MetaTrader 5 esté instalado y abierto."
            )
            return False

        # Obtener info de la cuenta
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("No se pudo obtener información de la cuenta.")
            mt5.shutdown()
            return False

        self.connected = True

        self.logger.separator("═")
        self.logger.success("CONECTADO A METATRADER 5")
        self.logger.info(f"  Cuenta:    {account_info.login}")
        self.logger.info(f"  Servidor:  {account_info.server}")
        self.logger.info(f"  Nombre:    {account_info.name}")
        self.logger.info(f"  Balance:   ${account_info.balance:,.2f}")
        self.logger.info(f"  Equity:    ${account_info.equity:,.2f}")
        self.logger.info(f"  Leverage:  1:{account_info.leverage}")
        self.logger.separator("═")

        return True

    def disconnect(self):
        """Cierra la conexión con MT5"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            self.logger.info("Desconectado de MetaTrader 5")

    def is_connected(self) -> bool:
        """Verifica si la conexión está activa"""
        if not self.connected:
            return False

        # Verificar que MT5 responde
        account_info = mt5.account_info()
        if account_info is None:
            self.connected = False
            self.logger.error("Se perdió la conexión con MT5")
            return False

        return True

    def get_account_info(self) -> dict | None:
        """Retorna información de la cuenta como diccionario"""
        if not self.is_connected():
            return None

        info = mt5.account_info()
        if info is None:
            return None

        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "margin_level": info.margin_level,
            "profit": info.profit,
            "server": info.server,
        }

    def ensure_symbol_available(self, symbol: str) -> bool:
        """Asegura que un símbolo esté disponible para trading"""
        symbol_info = mt5.symbol_info(symbol)

        if symbol_info is None:
            self.logger.error(f"Símbolo {symbol} no encontrado")
            return False

        if not symbol_info.visible:
            # Intentar habilitar el símbolo
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"No se pudo habilitar {symbol}")
                return False
            self.logger.info(f"Símbolo {symbol} habilitado")

        return True
