import logging
from config.settings import DashboardConfig
from dashboard.app import app, socketio, bot_logger
import threading

class FakeLogger:
    def info(self, msg): print(msg)
    def warning(self, msg): print(msg)
    def error(self, msg): print(msg)

from dashboard.app import run_dashboard
run_dashboard(FakeLogger())
