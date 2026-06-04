"""
🌐 Web Dashboard App
=========================
Flask server para monitorear el estado del bot en tiempo real.
Se ejecuta en un thread separado desde main.py.
"""

import threading
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash
from functools import wraps
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
    "profit_target": 0.0,
    "profitable_days": 0,
    "min_days": 0,
    "consistency_met": True,
    "total_trades": 0,
    "win_rate": 0.0,
    "equity_history": [],
    "open_positions": [],
    "live_exposures": {},
    "last_update": "",
    "latency_ms": 0.0,
    "logs": [],
}

import os
import sys

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'dashboard', 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)
app.config["SECRET_KEY"] = DashboardConfig.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")
logger = None


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@socketio.on("connect")
def handle_connect():
    """Envía datos actuales inmediatamente al conectarse un cliente"""
    # 🔴 FIX DE SEGURIDAD CRÍTICA (Unknown Unknown):
    # La ruta "/" estaba protegida, pero el WebSocket estaba desnudo al internet.
    # Cualquiera con un script podía conectarse a tu IP y espiar tu balance y trades en vivo.
    if not session.get("logged_in"):
        logger.warning("Fuga de datos prevenida: Cierre forzoso de WS por falta de sesión.")
        return False # Rechazar conexión

    socketio.emit("update", dashboard_data)
    # Enviar logs existentes
    for log_entry in dashboard_data.get("logs", []):
        socketio.emit("log", log_entry)


def update_dashboard_data(new_data: dict):
    """Actualiza los datos del dashboard y emite evento"""
    global dashboard_data
    
    # Manejar equity history temporal (últimos 50 puntos para no usar memoria)
    if "equity" in new_data:
        current_time = new_data.get("last_update", "00:00")
        current_equity = new_data["equity"]
        
        # Evitar duplicados seguidos
        if not dashboard_data["equity_history"] or dashboard_data["equity_history"][-1]["time"] != current_time:
             dashboard_data["equity_history"].append({"time": current_time, "equity": current_equity})
             
        if len(dashboard_data["equity_history"]) > 50:
            dashboard_data["equity_history"].pop(0)

    dashboard_data.update(new_data)
    socketio.emit("update", dashboard_data)


def add_dashboard_log(message: str, level: str = "INFO"):
    """Agrega un log al dashboard"""
    global dashboard_data
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from config.settings import BotConfig

    tz = ZoneInfo(BotConfig.TIMEZONE)
    log_entry = {
        "timestamp": datetime.now(tz).strftime("%H:%M:%S"),
        "message": message,
        "level": level,
    }
    dashboard_data["logs"].append(log_entry)
    # Keep only last 100 logs
    if len(dashboard_data["logs"]) > 100:
        dashboard_data["logs"].pop(0)

    socketio.emit("log", log_entry)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username")
        password = request.form.get("password")
        
        # 1. Validar Admin
        if user == DashboardConfig.USERNAME and password == DashboardConfig.PASSWORD:
            session["logged_in"] = True
            session["is_guest"] = False
            return redirect(url_for("index"))
            
        # 2. Validar Invitado
        elif user == DashboardConfig.GUEST_USERNAME and password == DashboardConfig.GUEST_PASSWORD:
            session["logged_in"] = True
            session["is_guest"] = True
            return redirect(url_for("index"))
            
        else:
            flash("Credenciales incorrectas", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/status")
@login_required
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

    # Lanzar navegador automáticamente en modo App
    def _open_browser():
        import time, os
        time.sleep(3) # Esperar a que Flask levante
        url = f"http://localhost:{DashboardConfig.PORT}"
        # Intenta Chrome modo App, si falla intenta Edge, si falla abre pestaña normal
        os.system(f'start chrome --app={url} || start msedge --app={url} || start {url}')
        
    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        socketio.run(
            app,
            host=DashboardConfig.HOST,
            port=int(DashboardConfig.PORT),
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except TypeError:
        # Fallback para versiones antiguas de Flask-SocketIO que no soportan allow_unsafe_werkzeug
        logger.warning("Flask-SocketIO TypeError emitido. Intentando sin parámetros modernos...")
        try:
            socketio.run(
                app,
                host=DashboardConfig.HOST,
                port=int(DashboardConfig.PORT),
                debug=False,
                use_reloader=False
            )
        except Exception as fallback_e:
            logger.error(f"❌ Error crítico levantando el Dashboard (Fallback 1): {fallback_e}")
            try:
                logger.warning("🔄 Intentando Fallback 2: Servidor nativo Flask puro (Sin WebSockets)...")
                app.run(
                    host=DashboardConfig.HOST,
                    port=int(DashboardConfig.PORT),
                    debug=False,
                    use_reloader=False
                )
            except BaseException as e2:
                logger.error(f"❌ FALLO TOTAL del Dashboard: {e2}")
    except BaseException as e:
        logger.error(f"❌ Error crítico levantando el Dashboard: {e}")
