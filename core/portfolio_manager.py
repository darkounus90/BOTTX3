import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict
from config.settings import BotConfig
from utils.logger import BotLogger

class PortfolioManager:
    """
    Mapa de Calor Volumétrico (Portfolio Rebalancing)
    Escanea la Watchlist entera una vez al día para descubrir
    qué divisa tiene mayor capital fluido y le aumenta el lotaje dinámicamente.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.heatmap: Dict[str, float] = {}

    def recalculate_heatmap(self) -> Dict[str, float]:
        """
        Descarga las últimas 10 velas D1 (Diarias) de todos los pares y calcula su 
        rango verdadero promedio (ADR) vs el precio. 
        Asigna un multiplicador de Kelly proporcional al volumen/volatilidad seguro.
        """
        self.logger.info("🔄 Calculando Mapa de Calor Volumétrico para rebalanceo...")
        volatility_scores = {}
        total_score = 0
        
        for symbol in BotConfig.WATCHLIST:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 10)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['range'] = (df['high'] - df['low']) / df['close'] * 10000 # Rango estandarizado
                score = df['range'].mean()
                volatility_scores[symbol] = score
                total_score += score
                
        if total_score == 0:
            for s in BotConfig.WATCHLIST:
                self.heatmap[s] = 1.0 # Base normal
            return self.heatmap
            
        # Distribuir multiplicador centrado en 1.0
        # (El par más volátil recibe hasta 1.2x del Kelly, el menor recibe 0.8x)
        weights = {}
        for s, score in volatility_scores.items():
            base_ratio = score / (total_score / len(volatility_scores))
            # Limitamos el peso (max 1.2, min 0.8) para evitar sobre/sub apalancamiento ridículo
            weights[s] = max(0.8, min(1.2, base_ratio))
            
        self.heatmap = weights
        return self.heatmap
        
    def get_weight(self, symbol: str) -> float:
        """Devuelve el multiplicador de riesgo para la moneda."""
        if not self.heatmap:
            self.recalculate_heatmap()
        return self.heatmap.get(symbol, 1.0)
