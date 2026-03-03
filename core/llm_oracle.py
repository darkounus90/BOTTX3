"""
🧠 LLM Oracle - Conciencia Artificial Institucional (CIO)
=========================================================
Actúa como Chief Investment Officer (CIO).
Recibe las señales frías del modelo estadístico técnico (Quant)
y las evalúa cognitivamente usando la API de Gemini de Google.
Si Gemini detecta que el contexto macro es suicida o el Technical
Analysis del Bot choca contra la lógica institucional (SMC/ICT), lo veta.
"""

import os
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from utils.logger import BotLogger
from config.settings import BotConfig

class GeminiOracle:
    """
    🧠 Motor de Conciencia Institucional Jerárquico.
    ===============================================
    Implementa:
    1. Two-Tier AI: 8B para salud, 2.0-Flash para trades.
    2. Local Rate Limiting: Evita bloqueos 429 de Google.
    3. Context Caching: Ahorro de tokens por vela M5.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.enabled = BotConfig.ORACLE_ENABLED
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        
        self.system_ready = False
        self._last_warning_time = datetime.min
        
        # Rate Limiting (Token Bucket)
        self.rpm_limit = 14  # Max 14 por minuto (margen de seguridad)
        self.tokens = self.rpm_limit
        self.last_refill = time.time()
        
        # Cache de señales (para no preguntar lo mismo en la misma vela)
        self._signal_cache = {} # {symbol: (candle_time, decision)}

        if self.enabled:
            if not self.api_key or genai is None:
                self.logger.warning("⚠️ Oracle Engine manual: Falta API Key. Operando modo Quant Puro.")
                self.enabled = False
            else:
                try:
                    genai.configure(api_key=self.api_key)
                    
                    # --- DESCUBRIMIENTO DINÁMICO DE MODELOS ---
                    available_models = [m.name.replace("models/", "") for m in genai.list_models() 
                                       if "generateContent" in m.supported_generation_methods]
                    
                    # 1. Seleccionar Tier 2 (Critical - Prioridad 2.0-flash)
                    tier2_candidates = [m for m in available_models if "2.0-flash" in m and "lite" not in m and "experimental" not in m]
                    self.target_critical = tier2_candidates[0] if tier2_candidates else "gemini-2.0-flash"
                    
                    # 2. Seleccionar Tier 1 (Light - Prioridad 1.5-flash)
                    tier1_candidates = [m for m in available_models if "1.5-flash" in m and "8b" in m] # Intentamos 8b primero
                    if not tier1_candidates:
                        tier1_candidates = [m for m in available_models if "1.5-flash" in m]
                    self.target_light = tier1_candidates[0] if tier1_candidates else "gemini-1.5-flash"
                    
                    # Inicializar modelos con los nombres validados
                    self.model_light = genai.GenerativeModel(model_name=self.target_light)
                    self.model_critical = genai.GenerativeModel(model_name=self.target_critical)
                    
                    self.system_ready = True
                    self.logger.success(f"👁️‍🗨️ AI ORACLE: Tier1={self.target_light} | Tier2={self.target_critical}")
                except Exception as e:
                    self.logger.error(f"Error inicializando Gemini Oracle: {e}")
                    self.enabled = False

    def _get_token(self) -> bool:
        """Implementación de Token Bucket para RPM"""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Recargar 1 token cada (60/rpm_limit) segundos
        self.tokens += elapsed * (self.rpm_limit / 60.0)
        if self.tokens > self.rpm_limit:
            self.tokens = self.rpm_limit
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

    def _call_model(self, model, prompt, urgent=False):
        """Wrapper con Rate Limit y Backoff"""
        if not self.system_ready: return None
        
        # Si no hay tokens, esperar si es urgente o abortar
        if not self._get_token():
            if urgent:
                time.sleep(5) # Espera proactiva
            else:
                return None

        # Reintento exponencial simple
        for attempt in range(2):
            try:
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    if (datetime.now() - self._last_warning_time).total_seconds() > 1800:
                        self.logger.warning(f"⚠️ Quota excedida en Google AI Studio (Tier de API).")
                        self._last_warning_time = datetime.now()
                    time.sleep(2 * (attempt + 1))
                    continue
                self.logger.error(f"Error en llamada AI: {e}")
                break
        return None

    def evaluate_trade(self, symbol: str, signal_type: str, reason: str, adx: float = None) -> dict:
        """Veto CIO (Tier 2 - Critical)"""
        if not self.enabled or not self.system_ready:
            return {"decision": "APPROVED", "reason": "Oracle Bypass (Disabled)"}

        # 1. VERIFICAR CACHÉ (Evitar spam por vela M5)
        # Obtenemos la hora de la vela actual (redondeada a 5 min)
        now_nyc = datetime.now(ZoneInfo("America/New_York"))
        candle_key = now_nyc.strftime("%Y%m%d%H") + str(now_nyc.minute // 5)
        
        cache_id = f"{symbol}_{signal_type}"
        if cache_id in self._signal_cache:
            last_candle, last_decision = self._signal_cache[cache_id]
            if last_candle == candle_key:
                return last_decision

        # 2. PREPARAR CONTEXTO MTF
        context_data = "N/A"
        try:
            import MetaTrader5 as mt5
            import pandas as pd
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 1)
            if rates is not None:
                context_data = f"H1_Trend: {'BULLISH' if rates[0]['close'] > rates[0]['open'] else 'BEARISH'}"
        except: pass

        prompt = (
            f"ERES CIO DE HEDGE FUND. Símbolo: {symbol} | Sentido: {signal_type} | Contexto: {context_data} | Técnica: {reason} | ADX: {adx}\n"
            f"Veta el trade si ves riesgo estructural (Liquidity Grab o contratendencia H1).\n"
            f"RESPONDE SOLO JSON: {{'decision':'APPROVED|REJECTED', 'reason':'motivo max 8 palabras', 'confidence':0-100}}"
        )

        resp_text = self._call_model(self.model_critical, prompt, urgent=True)
        
        if not resp_text:
            return {"decision": "APPROVED", "reason": "Quant Bypass (Rate Limit)"}

        try:
            # Limpiar posibles bloques de markdown
            clean_text = resp_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            data["decision"] = data.get("decision", "APPROVED").upper()
            
            # Guardar en Caché
            self._signal_cache[cache_id] = (candle_key, data)
            return data
        except:
            return {"decision": "APPROVED", "reason": "IA Parsing Error"}

    def evaluate_system_health(self, metrics: dict) -> str:
        """Diagnóstico Médico (Tier 1 - Light)"""
        if not self.enabled: return "⚠️ Dr. Quant offline."
        
        prompt = (
            f"ERES DR. QUANT. Diagnostica: Uptime {metrics.get('uptime')}, Loss: ${metrics.get('overall_dd')}, MT5: {metrics.get('mt5_connected')}.\n"
            f"Responde corto (1 párrafo) de diagnóstico y 1 consejo."
        )
        
        resp = self._call_model(self.model_light, prompt, urgent=False)
        return resp if resp else "🏥 Dr. Quant ocupado. Sistema estable en reporte técnico."

    def ask_oracle(self, question: str) -> str:
        """Consultas Generales (Usa Tier 1 para ahorrar cuota de Tier 2)"""
        if not self.enabled: return "⚠️ Oráculo apagado."
        
        prompt = f"Analista Pro respondiendo: {question}. Responde en 2 párrafos Max con emojis."
        resp = self._call_model(self.model_light, prompt, urgent=True)
        return resp if resp else "⚠️ Oráculo pensando demasiado. Intenta luego."
