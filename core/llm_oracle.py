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
        
        # Mapeo de Límites conocidos (Free Tier AI Studio)
        self.MODEL_CONFIGS = {
            "gemini-2.0-flash": {"rpm": 14, "rpd": 1500},
            "gemini-1.5-flash": {"rpm": 14, "rpd": 1500},
            "gemini-1.5-flash-8b": {"rpm": 14, "rpd": 1500},
            "gemini-2.0-flash-lite": {"rpm": 10, "rpd": 1500},
            "gemini-2.5-flash": {"rpm": 14, "rpd": 1500},
            "gemini-3-flash": {"rpm": 5, "rpd": 1500}, # Asumimos conservador para v3
            "default": {"rpm": 10, "rpd": 1500}
        }
        
        # Estado de los Buckets por Tier
        self.buckets = {
            "light": {"tokens": 10, "last_refill": time.time(), "rpm": 10, "rpd_count": 0},
            "critical": {"tokens": 14, "last_refill": time.time(), "rpm": 14, "rpd_count": 0}
        }

        if self.enabled:
            # (El bloque anterior de configure y descubrimiento dinámico se mantiene igual, 
            # pero actualizaremos los buckets con los modelos detectados)
            self._setup_system()

    def _setup_system(self):
        """Inicializa modelos y configura sus buckets específicos"""
        if not self.api_key or genai is None:
            self.enabled = False
            return

        try:
            genai.configure(api_key=self.api_key)
            raw_models = list(genai.list_models())
            available_models = [m.name for m in raw_models if "generateContent" in m.supported_generation_methods]
            
            if not available_models:
                self.logger.error("❌ Oráculo: Sin modelos disponibles.")
                self.enabled = False
                return

            # Selección de modelos (Logica similar a la anterior)
            t2_cands = [m for m in available_models if any(v in m for v in ["3.0", "2.5", "2.0"]) and "flash" in m]
            self.target_critical = t2_cands[0] if t2_cands else available_models[0]
            
            t1_cands = [m for m in available_models if "lite" in m or "8b" in m or "1.5-flash" in m]
            self.target_light = t1_cands[0] if t1_cands else self.target_critical
            
            # Configurar Buckets basados en el nombre del modelo
            for tier, model_name in [("light", self.target_light), ("critical", self.target_critical)]:
                config = next((v for k, v in self.MODEL_CONFIGS.items() if k in model_name), self.MODEL_CONFIGS["default"])
                self.buckets[tier]["rpm"] = config["rpm"]
                self.buckets[tier]["tokens"] = config["rpm"]
                self.buckets[tier]["rpd_limit"] = config["rpd"]
            
            self.model_light = genai.GenerativeModel(model_name=self.target_light)
            self.model_critical = genai.GenerativeModel(model_name=self.target_critical)
            
            self.system_ready = True
            self.logger.success(f"👁️‍🗨️ IA ORACLE: Tier 1 ({self.target_light}) RPM:{self.buckets['light']['rpm']}")
            self.logger.success(f"👁️‍🗨️ IA ORACLE: Tier 2 ({self.target_critical}) RPM:{self.buckets['critical']['rpm']}")
        except Exception as e:
            self.logger.error(f"Error configuración Oráculo: {e}")
            self.enabled = False

    def _get_token(self, tier: str) -> bool:
        """Token Bucket específico por Tier"""
        bucket = self.buckets.get(tier)
        if not bucket: return False
        
        now = time.time()
        elapsed = now - bucket["last_refill"]
        
        # Rellenar
        bucket["tokens"] += elapsed * (bucket["rpm"] / 60.0)
        if bucket["tokens"] > bucket["rpm"]:
            bucket["tokens"] = bucket["rpm"]
        
        bucket["last_refill"] = now

        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            bucket["rpd_count"] += 1
            return True
        return False

    def _call_model(self, model, prompt, tier="light", urgent=False):
        """Wrapper con Rate Limit por Tier"""
        if not self.system_ready: return None
        
        if not self._get_token(tier):
            if urgent:
                time.sleep(5)
                return self._call_model(model, prompt, tier, urgent) # Reintento directo para urgentes
            return None

        for attempt in range(2):
            try:
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    time.sleep(3 * (attempt + 1))
                    continue
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

        resp_text = self._call_model(self.model_critical, prompt, tier="critical", urgent=True)
        
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
        
        resp = self._call_model(self.model_light, prompt, tier="light", urgent=False)
        return resp if resp else "🏥 Dr. Quant ocupado. Sistema estable en reporte técnico."

    def ask_oracle(self, question: str) -> str:
        """Consultas Generales (Usa Tier 1 para ahorrar cuota de Tier 2)"""
        if not self.enabled: return "⚠️ Oráculo apagado."
        
        prompt = f"Analista Pro respondiendo: {question}. Responde en 2 párrafos Max con emojis."
        resp = self._call_model(self.model_light, prompt, tier="light", urgent=True)
        return resp if resp else "⚠️ Oráculo pensando demasiado. Intenta luego."

    def re_init(self, new_key: str) -> bool:
        """Permite actualizar la API Key en caliente desde Telegram"""
        self.api_key = new_key
        # Actualizar variable de entorno para persistencia en esta sesión
        os.environ["GEMINI_API_KEY"] = new_key
        
        if not self.api_key or genai is None:
            self.logger.warning("Falla en re-init: API Key vacía o librería ausente.")
            return False
            
        try:
            genai.configure(api_key=self.api_key)
            
            # --- DESCUBRIMIENTO DINÁMICO DE MODELOS ---
            raw_models = list(genai.list_models())
            available_models = [m.name for m in raw_models if "generateContent" in m.supported_generation_methods]
            
            if not available_models:
                self.logger.error("❌ Oráculo (Re-init): No se encontraron modelos compatibles.")
                return False

            # 1. Seleccionar Tier 2 (Critical)
            tier2_candidates = [m for m in available_models if any(v in m for v in ["3.0", "2.5", "2.0"]) and "flash" in m]
            if not tier2_candidates:
                tier2_candidates = [m for m in available_models if "flash" in m]
            self.target_critical = tier2_candidates[0] if tier2_candidates else available_models[0]
            
            # 2. Seleccionar Tier 1 (Light)
            tier1_candidates = [m for m in available_models if "lite" in m or "8b" in m or "1.5-flash" in m]
            if not tier1_candidates:
                tier1_candidates = [m for m in available_models if "flash" in m and m != self.target_critical]
            self.target_light = tier1_candidates[0] if tier1_candidates else self.target_critical
            
            # Inicializar modelos
            self.model_light = genai.GenerativeModel(model_name=self.target_light)
            self.model_critical = genai.GenerativeModel(model_name=self.target_critical)
            
            self.system_ready = True
            self.enabled = True
            
            # Resetear Rate Limiter y Cache al cambiar de llave
            self.buckets["light"]["tokens"] = self.buckets["light"]["rpm"]
            self.buckets["critical"]["tokens"] = self.buckets["critical"]["rpm"]
            self._signal_cache = {}
            
            self.logger.success(f"🔑 Oráculo reconectado con nueva llave.")
            return True
        except Exception as e:
            self.logger.error(f"Error en re-init del Oráculo: {e}")
            return False
