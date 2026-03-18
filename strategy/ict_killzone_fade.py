import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from strategy.base_strategy import BaseStrategy
from config.settings import BotConfig
from utils.logger import BotLogger

class ICTKillzoneFadeStrategy(BaseStrategy):
    """
    🎯 ICT Kill Zone Fade (Módulo Opcional Futuro)
    =============================================
    Busca falsos rompimientos (Judas Swings) durante las sesiones
    clave de liquidez (London, New York, Asia), también conocidas como 
    'ICT Killzones'.

    Se activa tras una rápida recolección de liquidez en un máximo o
    mínimo de sesión, formando un Fair Value Gap (FVG) reversivo.
    """

    def __init__(self, logger: BotLogger, symbol: str = None):
        super().__init__(logger)
        self.symbol = symbol or BotConfig.DEFAULT_SYMBOL
        self.timeframe = mt5.TIMEFRAME_M5 # Se opera en LTF (Low Timeframe)
        self.bars_needed = 200 # Para rastrear el rango asiático o máximos previos

        # Definición de Killzones (Horario EST)
        self.london_killzone_start = 2
        self.london_killzone_end = 5
        self.ny_killzone_start = 7
        self.ny_killzone_end = 10
        self.asia_killzone_start = 20
        self.asia_killzone_end = 0

    def get_name(self) -> str:
        return f"ICT Kill Zone Fade ({self.symbol})"

    def _is_in_killzone(self) -> bool:
        """Verifica si la hora actual de New York está dentro de una Killzone"""
        hour_est = datetime.now(ZoneInfo("America/New_York")).hour
        
        in_london = self.london_killzone_start <= hour_est < self.london_killzone_end
        in_ny = self.ny_killzone_start <= hour_est < self.ny_killzone_end
        in_asia = hour_est >= self.asia_killzone_start or hour_est < self.asia_killzone_end
        
        return in_london or in_ny or in_asia

    def generate_signal(self) -> dict | None:
        """Lógica principal de generación de la señal ICT Fade"""
        
        # 0. Verificamos Filtro Temporal (Solo Killzones)
        if not self._is_in_killzone():
            return None

        # 1. Obtener Data
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, self.bars_needed)
        if rates is None or len(rates) < self.bars_needed:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # Variables de tiempo de la vela actual
        last_closed = df.iloc[-2]
        prev_closed = df.iloc[-3]
        
        # --- 2. DEFINIR RANGO DE LIQUIDEZ PREVIO (Asian Session / Recent Swings) ---
        # Miramos 60 velas atrás (5 horas) descartando las últimas 5 velas para encontrar el nivel de barrido (Swing High/Low).
        lookback_df = df.iloc[-65:-5]
        asian_high = lookback_df['high'].max()
        asian_low = lookback_df['low'].min()
        
        # --- 3. DETECCIÓN DE JUDAS SWING (LIQUIDITY SWEEP) ---
        # Verificar si en las últimas 5 velas el precio rompió el alto o bajo para atrapar liquidez
        recent_df = df.iloc[-5:-1]
        sweep_high = recent_df['high'].max() >= asian_high
        sweep_low = recent_df['low'].min() <= asian_low

        # --- 4. DETECCIÓN DE FAIR VALUE GAP (FVG) ---
        # FVG Alcista (Bullish FVG): Vela 1 Alta < Vela 3 Baja
        # FVG Bajista (Bearish FVG): Vela 1 Baja > Vela 3 Alta
        # Evaluamos el patrón de 3 velas: [-4], [-3], [-2] (las cerradas más recientes)
        v1 = df.iloc[-4]
        v2 = df.iloc[-3]
        v3 = df.iloc[-2]

        bullish_fvg = v1['high'] < v3['low'] and v3['close'] > v2['open']  # Se requiere confirmación alcista
        bearish_fvg = v1['low'] > v3['high'] and v3['close'] < v2['open']  # Se requiere confirmación bajista

        signal_type = None
        reason = ""
        
        # ATR para Risk Management
        atr = df['high'].iloc[-14:] - df['low'].iloc[-14:]
        current_atr = atr.mean()
        
        # LÓGICA DE GATILLO:
        # 1. Barre mínimo (Liquidity Purge) y forma un FVG Alcista -> BUY
        if sweep_low and bullish_fvg:
            # Filtro adicional: El cuerpo de la última vela cerrada (v3) cerró fuerte
            if v3['close'] > v3['open']:
                signal_type = "BUY"
                reason = "ICT Judas Swing | Liquidity Sweep (L) + Bullish FVG"
                
        # 2. Barre máximo (Buy Stops Purge) y forma un FVG Bajista -> SELL
        elif sweep_high and bearish_fvg:
            if v3['close'] < v3['open']:
                signal_type = "SELL"
                reason = "ICT Judas Swing | Liquidity Sweep (H) + Bearish FVG"

        if not signal_type:
            return None

        # --- EVITAR SPAM EN LA MISMA VELA ---
        current_candle_time = last_closed['time']
        if getattr(self, 'last_signal_time', None) == current_candle_time:
            return None
        self.last_signal_time = current_candle_time

        # --- GESTIÓN DE RIESGO: SL ESTRUCTURAL ICT ---
        symbol_info = mt5.symbol_info(self.symbol)
        point = symbol_info.point if symbol_info and symbol_info.point else 0.00001
        
        # En ICT el Stop Loss original suele ir debajo de la mecha del sweep.
        # Aproximamos con un SL fijo basado en ATR o el tamaño del Sweep
        sl_pip_dist = (current_atr * 1.5) / (point * 10)
        tp_pip_dist = (current_atr * 3.5) / (point * 10)  # ICT R:R mínimo de 1:2 o más

        sl_pips = max(round(sl_pip_dist, 1), 10.0)
        tp_pips = max(round(tp_pip_dist, 1), 25.0)

        ts_signal = {
            "signal": signal_type,
            "symbol": self.symbol,
            "stop_loss_pips": sl_pips,
            "take_profit_pips": tp_pips,
            "reason": reason
        }

        self.log_signal(ts_signal)
        return ts_signal
