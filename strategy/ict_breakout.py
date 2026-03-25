import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from zoneinfo import ZoneInfo
from config.settings import BotConfig

class ICTBreakoutStrategy:
    """
    Estrategia Institucional: Smart Money Concepts (ICT)
    - Opera exclusivamente en la apertura de Nueva York (Killzone: 8am - 11am EST)
    - Busca neutralización de liquidez (Judas Swing) y retorno rápido.
    """

    def __init__(self, symbol: str, logger):
        self.symbol = symbol
        self.logger = logger
        self.lookback_asian_candles = 96 # 8 horas en M5
        self.fvg_tolerance_pips = 2.0
        
        # Parámetros asimétricos para la cacería de tendencias
        self.stop_loss_pips_base = 8.0   # SL Super ajustado
        self.take_profit_pips_base = 25.0 # TP Exigente (Risk:Reward ~ 1:3)

    def generate_signal(self) -> dict | None:
        """
        Calcula la señal usando patrones de SMC en M5
        """
        # --- 1. FILTRO HORARIO INQUEBRANTABLE (NY Morning Killzone) ---
        hour_est = datetime.now(ZoneInfo("America/New_York")).hour
        if hour_est < 8 or hour_est >= 11:
            return None

        # --- 2. OBTENER DATOS (Arquitectura limpia Data-Access) ---
        rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M5, 0, self.lookback_asian_candles + 10)
        if rates is None or len(rates) < self.lookback_asian_candles:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Evitar operar la vela viva
        last_closed = df.iloc[-2]
        
        # --- 3. LÓGICA DE NEGOCIO PURE DOMAIN (SMC) ---
        # Calcular el rango de liquidez anterior (High/Low de las últimas 8 hrs)
        asian_high = df['high'].iloc[-(self.lookback_asian_candles+2):-2].max()
        asian_low = df['low'].iloc[-(self.lookback_asian_candles+2):-2].min()

        signal_type = None
        reason = ""

        # DETECCIÓN TIPO A: Compra (Judas Swing a la baja)
        # Si la vela violó el mínimo asiático (trampa) y cerró fuertemente al alza
        if last_closed['low'] < asian_low and last_closed['close'] > asian_low:
            body = abs(last_closed['close'] - last_closed['open'])
            total = last_closed['high'] - last_closed['low']
            # Exigir que sea un rechazo contundente
            if body > total * 0.4 and last_closed['close'] > last_closed['open']:
                signal_type = "BUY"
                reason = "Judas Swing Bajista + ChoCh Alcista M5"

        # DETECCIÓN TIPO B: Venta (Judas Swing al alza)
        elif last_closed['high'] > asian_high and last_closed['close'] < asian_high:
            body = abs(last_closed['close'] - last_closed['open'])
            total = last_closed['high'] - last_closed['low']
            if body > total * 0.4 and last_closed['close'] < last_closed['open']:
                signal_type = "SELL"
                reason = "Judas Swing Alcista + ChoCh Bajista M5"

        if not signal_type:
            return None

        # --- 4. VALIDADOR FINAL Y ESTRUCTURA ZOD-LIKE ---
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return None

        # Cálculo asimétrico de Risk:Reward
        atr_14 = df['high'].iloc[-15:-1].max() - df['low'].iloc[-15:-1].min() # ATR simplificado rápido
        pip_size = symbol_info.point * (10 if symbol_info.digits in [3, 5] else 1)
        atr_pips = (atr_14 / pip_size) if pip_size > 0 else 10.0
        
        # Envoltorio de Riesgo estructurado
        sl_pips = max(self.stop_loss_pips_base, round(atr_pips * 0.5, 1))
        tp_pips = max(self.take_profit_pips_base, round(sl_pips * 3.0, 1))

        # Loggeado estructurado (Pino-style inspired)
        self.logger.info(
            f"🎯 Setup SMC ICT Detectado! | Símbolo: {self.symbol} | "
            f"Tipo: {signal_type} | Razón: {reason} | Riesgo: {sl_pips}pips | Beneficio: {tp_pips}pips"
        )
        
        return {
            "symbol": self.symbol,
            "type": signal_type,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "probability": 80.0,
            "reason": reason,
            "strategy_tag": "SMC_BREAKOUT"
        }
