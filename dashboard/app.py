"""
🌐 Web Dashboard App
=========================
Flask server para monitorear el estado del bot en tiempo real.
Se ejecuta en un thread separado desde main.py.
"""

import threading
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from config.settings import DashboardConfig
from utils.logger import BotLogger

# Global storage for dashboard data
dashboard_data = {
    "status": "STOPPED",
    "phase": 0,
    "balance": 0.0,
    "equity": 0.0,
    "daily_profit": 0.0,
    "daily_dd": 0.0,
    "overall_dd": 0.0,
    "open_positions": [],
    "last_update": "",
    "logs": [],
}

app = Flask(__name__)
app.config["SECRET_KEY"] = DashboardConfig.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")
logger = None


def update_dashboard_data(new_data: dict):
    """Actualiza los datos del dashboard y emite evento"""
    global dashboard_data
    dashboard_data.update(new_data)
    socketio.emit("update", dashboard_data)


def add_dashboard_log(message: str, level: str = "INFO"):
    """Agrega un log al dashboard"""
    global dashboard_data
    log_entry = {
        "timestamp": message.split("|")[0].strip() if "|" in message else "",
        "message": message,
        "level": level,
    }
    dashboard_data["logs"].append(log_entry)
    # Keep only last 100 logs
    if len(dashboard_data["logs"]) > 100:
        dashboard_data["logs"].pop(0)

    socketio.emit("log", log_entry)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def get_status():
    return jsonify(dashboard_data)


def run_dashboard(bot_logger: BotLogger):
    """Ejecuta el servidor Flask en un thread"""
    global logger
    logger = bot_logger
    logger.info(f"🌐 Dashboard iniciando en http://{DashboardConfig.HOST}:{DashboardConfig.PORT}")

    # Desactivar logs de werkzeug para no saturar la consola
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    socketio.run(
        app,
        host=DashboardConfig.HOST,
        port=DashboardConfig.PORT,
        debug=False,
        use_reloader=False,
    )
