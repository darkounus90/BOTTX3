"""
🔗 Correlation Manager - Motor Anti-Correlación Institucional (FTMO Compliant)
===============================================================================
Calcula la Exposición Neta por Divisa (Net Currency Exposure) y la Correlación
Estadística de Pearson en tiempo real para evitar sobre-apalancamiento 
direccional involuntario.

Ejemplo Crítico:
    - BUY EURUSD = +EUR / -USD  
    - BUY GBPUSD = +GBP / -USD  
    → Exposición Neta: -2x USD (Doble apuesta contra el Dólar)
    → Si DXY sube, AMBAS posiciones mueren juntas.

Este módulo lo previene calculando cuánto estás "vendido" o "comprado" de cada
divisa individual, bloqueando nuevas entradas que aumenten la concentración.
"""

import MetaTrader5 as mt5
import numpy as np
from datetime import datetime
from typing import Dict, Tuple, Optional
from config.settings import BotConfig
from utils.logger import BotLogger


class CorrelationManager:
    """
    Motor Cuantitativo de Gestión de Correlación.
    
    Funcionalidades:
    1. Net Currency Exposure: Mide la exposición neta por divisa individual.
    2. Correlación de Pearson: Calcula la correlación estadística entre pares.
    3. Bloqueo Direccional Inteligente: Solo bloquea si la nueva operación
       AUMENTA la concentración en la misma dirección.
    """

    # Umbral de correlación absoluta para considerar dos pares "peligrosamente correlacionados"
    CORRELATION_THRESHOLD = 0.75
    
    # Máxima exposición neta permitida por divisa (en unidades de "posiciones equivalentes")
    # Ej: si MAX_NET_EXPOSURE = 1.5, puedes tener hasta 1.5 lotes netos en una sola dirección por divisa
    MAX_NET_EXPOSURE = 1.5

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self._correlation_cache: Dict[str, float] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_minutes = 60  # Recalcular correlaciones cada hora

    def get_currency_exposure(self) -> Dict[str, float]:
        """
        Calcula la Exposición Neta por Divisa de todas las posiciones abiertas del bot.
        
        Returns:
            Dict con cada divisa y su exposición neta en lotes.
            Positivo = Comprado (Long), Negativo = Vendido (Short).
            
        Ejemplo:
            {'EUR': +0.50, 'USD': -1.20, 'GBP': +0.70}
            → Estás muy vendido en USD (peligro si DXY sube)
        """
        positions = mt5.positions_get()
        if not positions:
            return {}

        exposure: Dict[str, float] = {}

        for pos in positions:
            if pos.magic != BotConfig.MAGIC_NUMBER:
                continue

            base = pos.symbol[:3]   # EUR de EURUSD
            quote = pos.symbol[3:]  # USD de EURUSD
            volume = pos.volume

            if pos.type == mt5.ORDER_TYPE_BUY:
                # BUY EURUSD = Compras EUR, Vendes USD
                exposure[base] = exposure.get(base, 0.0) + volume
                exposure[quote] = exposure.get(quote, 0.0) - volume
            else:
                # SELL EURUSD = Vendes EUR, Compras USD
                exposure[base] = exposure.get(base, 0.0) - volume
                exposure[quote] = exposure.get(quote, 0.0) + volume

        return exposure

    def calculate_pearson_correlation(self, symbol_a: str, symbol_b: str, periods: int = 50) -> float:
        """
        Calcula la Correlación de Pearson entre dos pares de divisas
        usando los últimos N cierres de velas H1.
        
        Returns:
            Float entre -1.0 y 1.0
            +1.0 = Perfectamente correlacionados (se mueven juntos)
            -1.0 = Perfectamente inversamente correlacionados (se mueven en espejo)
             0.0 = Sin correlación
        """
        cache_key = f"{min(symbol_a, symbol_b)}_{max(symbol_a, symbol_b)}"
        
        # Verificar caché
        now = datetime.now()
        if (self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl_minutes * 60 and
            cache_key in self._correlation_cache):
            return self._correlation_cache[cache_key]

        try:
            rates_a = mt5.copy_rates_from_pos(symbol_a, mt5.TIMEFRAME_H1, 0, periods + 1)
            rates_b = mt5.copy_rates_from_pos(symbol_b, mt5.TIMEFRAME_H1, 0, periods + 1)

            if rates_a is None or rates_b is None:
                return 0.0
            if len(rates_a) < periods or len(rates_b) < periods:
                return 0.0

            # Calcular retornos logarítmicos (más preciso que retornos simples)
            closes_a = np.array([r['close'] for r in rates_a])
            closes_b = np.array([r['close'] for r in rates_b])

            returns_a = np.diff(np.log(closes_a))
            returns_b = np.diff(np.log(closes_b))

            # Alinear longitudes
            min_len = min(len(returns_a), len(returns_b))
            returns_a = returns_a[-min_len:]
            returns_b = returns_b[-min_len:]

            # Pearson
            if np.std(returns_a) == 0 or np.std(returns_b) == 0:
                return 0.0

            correlation = np.corrcoef(returns_a, returns_b)[0, 1]

            # Guardar en caché
            self._correlation_cache[cache_key] = float(correlation)
            self._cache_timestamp = now

            return float(correlation)

        except Exception as e:
            self.logger.error(f"Error calculando correlación {symbol_a}/{symbol_b}: {e}")
            return 0.0

    def check_new_trade_allowed(self, symbol: str, order_type: int) -> Tuple[bool, str]:
        """
        Evaluación integral antes de abrir una nueva posición.
        
        Verifica:
        1. Exposición Neta por Divisa (no sobre-apostar en una sola moneda)
        2. Correlación Estadística con posiciones existentes (misma dirección)
        
        Args:
            symbol: Par a operar (ej: "EURUSD")
            order_type: mt5.ORDER_TYPE_BUY o mt5.ORDER_TYPE_SELL
            
        Returns:
            Tuple[bool, str]: (Permitido, Razón)
        """
        # ═══════════════════════════════════════════════════════════════
        # FASE 1: Exposición Neta por Divisa
        # ═══════════════════════════════════════════════════════════════
        exposure = self.get_currency_exposure()
        
        if exposure:  # Solo si hay posiciones abiertas
            new_base = symbol[:3]
            new_quote = symbol[3:]

            # Simular el impacto de la nueva operación (con 1 lote como referencia)
            if order_type == mt5.ORDER_TYPE_BUY:
                projected_base = exposure.get(new_base, 0.0) + 1.0   # Compra base
                projected_quote = exposure.get(new_quote, 0.0) - 1.0  # Vende quote
            else:
                projected_base = exposure.get(new_base, 0.0) - 1.0   # Vende base
                projected_quote = exposure.get(new_quote, 0.0) + 1.0  # Compra quote

            # Verificar si la exposición proyectada excede el límite
            for currency, proj_exposure in [(new_base, projected_base), (new_quote, projected_quote)]:
                if abs(proj_exposure) > self.MAX_NET_EXPOSURE:
                    reason = (
                        f"🔗 CORRELACIÓN BLOQUEADA: {symbol} aumentaría la exposición "
                        f"neta de {currency} a {proj_exposure:+.2f} lotes "
                        f"(límite: ±{self.MAX_NET_EXPOSURE}). "
                        f"Exposición actual: {self._format_exposure(exposure)}"
                    )
                    self.logger.warning(reason)
                    return False, reason

        # ═══════════════════════════════════════════════════════════════
        # FASE 2: Correlación Estadística de Pearson
        # ═══════════════════════════════════════════════════════════════
        positions = mt5.positions_get()
        if positions:
            bot_symbols = set()
            for pos in positions:
                if pos.magic == BotConfig.MAGIC_NUMBER:
                    bot_symbols.add((pos.symbol, pos.type))
            
            for existing_symbol, existing_type in bot_symbols:
                if existing_symbol == symbol:
                    continue  # Ya manejado por MAX_OPEN_POSITIONS

                corr = self.calculate_pearson_correlation(symbol, existing_symbol)

                # Correlación positiva alta + misma dirección = PELIGRO
                if abs(corr) >= self.CORRELATION_THRESHOLD:
                    same_direction = (
                        (corr > 0 and order_type == existing_type) or
                        (corr < 0 and order_type != existing_type)
                    )
                    
                    if same_direction:
                        direction_str = "misma" if corr > 0 else "inversa"
                        reason = (
                            f"🔗 PEARSON BLOQUEADO: {symbol} tiene correlación "
                            f"{direction_str} de {corr:.2f} con {existing_symbol} "
                            f"(umbral: ±{self.CORRELATION_THRESHOLD}). "
                            f"Ambas posiciones irían en la misma dirección efectiva."
                        )
                        self.logger.warning(reason)
                        return False, reason

        # ═══════════════════════════════════════════════════════════════
        # APROBADO: La nueva operación diversifica el portafolio
        # ═══════════════════════════════════════════════════════════════
        return True, "Diversificación OK"

    def get_exposure_report(self) -> dict:
        """
        Genera un reporte de exposición para el Dashboard y Telegram.
        """
        exposure = self.get_currency_exposure()
        
        if not exposure:
            return {"status": "CLEAR", "currencies": {}, "risk_level": "LOW"}

        max_abs = max(abs(v) for v in exposure.values()) if exposure else 0
        
        if max_abs >= self.MAX_NET_EXPOSURE:
            risk_level = "CRITICAL"
        elif max_abs >= self.MAX_NET_EXPOSURE * 0.7:
            risk_level = "HIGH"
        elif max_abs >= self.MAX_NET_EXPOSURE * 0.4:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "status": "EXPOSED" if exposure else "CLEAR",
            "currencies": {k: round(v, 2) for k, v in sorted(exposure.items())},
            "risk_level": risk_level,
            "max_exposure": round(max_abs, 2),
            "limit": self.MAX_NET_EXPOSURE,
        }

    def _format_exposure(self, exposure: Dict[str, float]) -> str:
        """Formatea la exposición para logs legibles."""
        parts = []
        for currency, amount in sorted(exposure.items()):
            direction = "🟢 Long" if amount > 0 else "🔴 Short"
            parts.append(f"{currency}: {direction} {abs(amount):.2f}")
        return " | ".join(parts)
