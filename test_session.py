import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mocking modules
import sys
from unittest.mock import MagicMock
sys.modules['MetaTrader5'] = MagicMock()
sys.modules['dashboard.app'] = MagicMock()

from core.session_filter import SessionFilter
from utils.logger import BotLogger

logger = BotLogger()
sf = SessionFilter(logger)
print("Current session:", sf.get_current_session())
print("Is trading allowed?", sf.is_trading_allowed())
print("time_until_next_session:", sf.time_until_next_session())
print("get_session_info:", sf.get_session_info())
