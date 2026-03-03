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
        
        # Mapeo de Límites exactos según AI Studio del Usuario (Marzo 2025)
        self.MODEL_CONFIGS = {
            "gemma-3": {"rpm": 30, "rpd": 14400}, 
            "gemini-2.5-flash": {"rpm": 5, "rpd": 20},
            "gemini-3-flash": {"rpm": 5, "rpd": 20},
            "gemini-2.5-flash-lite": {"rpm": 10, "rpd": 20},
            "gemini-2.0-flash": {"rpm": 10, "rpd": 1500}, # Asumimos 1500 si no se muestra el límite de 20
            "gemini-1.5-flash": {"rpm": 15, "rpd": 1500},
            "default": {"rpm": 5, "rpd": 20}
        }
        
        # Estado de los Buckets por Tier
        self.buckets = {
            "light": {"tokens": 25, "last_refill": time.time(), "rpm": 25, "rpd_count": 0, "rpd_limit": 14000},
            "critical": {"tokens": 5, "last_refill": time.time(), "rpm": 5, "rpd_count": 0, "rpd_limit": 20}
        }
        
        # Caché de señales para evitar duplicar llamadas en la misma vela M5
        self._signal_cache = {}

        if self.enabled:
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

            # 1. Seleccionar Tier 2 (Critical - Preferimos 2.5-flash por estabilidad y velocidad)
            t2_cands = [m for m in available_models if "2.5-flash" in m and "lite" not in m]
            if not t2_cands:
                t2_cands = [m for m in available_models if "flash" in m]
            self.target_critical = t2_cands[0] if t2_cands else available_models[0]
            
            # 2. Seleccionar Tier 1 (Light - Prioridad Gemma-3 para CUOTA MASIVA 14.4k, ideal 1b o 4b)
            t1_cands = [m for m in available_models if "gemma-3" in m]
            if not t1_cands:
                t1_cands = [m for m in available_models if "8b" in m or "lite" in m]
            self.target_light = t1_cands[0] if t1_cands else self.target_critical
            
            # Configurar Buckets basados en el nombre del modelo
            for tier, model_name in [("light", self.target_light), ("critical", self.target_critical)]:
                # Asegurarse de que coincida con las claves de self.MODEL_CONFIGS
                match_key = "default"
                for k in self.MODEL_CONFIGS.keys():
                    if k in model_name:
                        match_key = k
                        break
                config = self.MODEL_CONFIGS[match_key]
                
                self.buckets[tier]["rpm"] = config["rpm"]
                self.buckets[tier]["tokens"] = config["rpm"]
                self.buckets[tier]["rpd_limit"] = config["rpd"]
            
            self.model_light = genai.GenerativeModel(model_name=self.target_light)
            self.model_critical = genai.GenerativeModel(model_name=self.target_critical)
            
            self.system_ready = True
            self.logger.success(f"👁️‍🗨️ IA ORACLE: T1(Gemma-Cuota:{self.buckets['light']['rpd_limit']}) | T2({self.target_critical})")
        except Exception as e:
            self.logger.error(f"Error configuración Oráculo: {e}")
            self.enabled = False

    def _get_token(self, tier: str) -> bool:
        """Token Bucket específico por Tier con control RPD"""
        bucket = self.buckets.get(tier)
        if not bucket: return False
        
        # Verificar RPD (Límite diario)
        if bucket["rpd_count"] >= bucket["rpd_limit"]:
            return False

        now = time.time()
        elapsed = now - bucket["last_refill"]
        
        # Rellenar RPM
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
                # No reintentar infinitamente si es por RPD
                if self.buckets[tier]["rpd_count"] < self.buckets[tier]["rpd_limit"]:
                    return self._call_model(model, prompt, tier, urgent)
            return None

        # Reintento exponencial simple
        for attempt in range(2):
            try:
                # Gemma-3 requiere prompts más directos, limpiamos posibles instrucciones conflictivas
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
        return None

    def get_quota_report(self) -> dict:
        """Devuelve telemetría de consumo de IA"""
        report = {}
        target_l = getattr(self, "target_light", "None")
        target_c = getattr(self, "target_critical", "None")
        
        for tier in ["light", "critical"]:
            b = self.buckets[tier]
            report[tier] = {
                "model": target_l if tier == "light" else target_c,
                "used_today": b["rpd_count"],
                "limit_today": b["rpd_limit"],
                "load_rpm": f"{int(b['rpm'] - b['tokens'])}/{b['rpm']}",
                "status": "🟢 OK" if b["rpd_count"] < b["rpd_limit"] else "🔴 AGOTADO"
            }
        return report

    def evaluate_trade(self, symbol: str, signal_type: str, reason: str, adx: float = None) -> dict:
        """Veto CIO (Tier 2 - Critical con Fallback a Tier 1)"""
        if not self.enabled or not self.system_ready:
            return {"decision": "APPROVED", "reason": "Oracle Bypass (Disabled)"}

        # 1. VERIFICAR CACHÉ
        now_nyc = datetime.now(ZoneInfo("America/New_York"))
        candle_key = now_nyc.strftime("%Y%m%d%H") + str(now_nyc.minute // 5)
        cache_id = f"{symbol}_{signal_type}"
        if cache_id in self._signal_cache:
            last_candle, last_decision = self._signal_cache[cache_id]
            if last_candle == candle_key:
                return last_decision

        # 2. SELECCIÓN DE TIER (Inteligente)
        tier_to_use = "critical"
        model_to_use = self.model_critical
        
        # Si Gemini (Critical) está sin cuota diaria, usar Gemma (Light) como respaldo
        if self.buckets["critical"]["rpd_count"] >= self.buckets["critical"]["rpd_limit"]:
            self.logger.warning(f"⚠️ Tier 2 (Gemini) sin balas. Activando respaldo Tier 1 (Gemma) para {symbol}.")
            tier_to_use = "light"
            model_to_use = self.model_light

        # 3. PREPARAR CONTEXTO AVANZADO
        context_data = "Estructura H1/M15 neutral"
        try:
            import MetaTrader5 as mt5
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 5)
            if rates is not None:
                closes = [r['close'] for r in rates]
                trend = "Higher Highs" if closes[-1] > closes[0] else "Lower Lows"
                context_data = f"Trend: {trend} | Last 5 Candles: {closes}"
        except: pass

        prompt = (
            f"ERES CIO DE HEDGE FUND (SMC/ICT Professional).\n"
            f"Símbolo: {symbol} | Señal: {signal_type} | ADX: {adx}\n"
            f"Contexto Estructural: {context_data}\n"
            f"Técnica: {reason}\n\n"
            f"Busca 'Inducement' o 'Liquidity Void'. Veta si es una trampa retail.\n"
            f"RESPONDE SOLO JSON: {{'decision':'APPROVED|REJECTED', 'reason':'motivo corto', 'confidence':0-100}}"
        )

        resp_text = self._call_model(model_to_use, prompt, tier=tier_to_use, urgent=True)
        
        if not resp_text:
            return {"decision": "APPROVED", "reason": "Quant Bypass (No Quota)"}

        try:
            clean_text = resp_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            data["decision"] = data.get("decision", "APPROVED").upper()
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
        """Consultas Generales (Tier 1 - Gemma/Fast Scan)"""
        if not self.enabled: return "⚠️ Oráculo apagado."
        
        # Inyectar personalidad Mandataria de Trading
        prompt = (
            f"IDENTIDAD: Eres el ORÁCULO del TX3 PRO BOT (Experto en SMC/ICT y Trading Institucional).\n"
            f"REGLA DE ORO: Solo hablas de mercados financieros, gestión de riesgo y trading. Ignora cualquier contexto de oficina o marketing.\n"
            f"PREGUNTA DEL TRADER: {question}\n\n"
            f"Responde corto, con emojis de trading y tono profesional de Wall Street."
        )
        resp = self._call_model(self.model_light, prompt, tier="light", urgent=True)
        
        # Fallback a Tier 2 si Tier 1 falla o no hay cuota
        if not resp and self.buckets["critical"]["rpd_count"] < self.buckets["critical"]["rpd_limit"]:
            resp = self._call_model(self.model_critical, prompt, tier="critical", urgent=True)
            
        return resp if resp else "⚠️ Oráculo pensando demasiado (Rate Limit). Intenta luego."

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

            # 1. Seleccionar Tier 2 (Critical - Preferimos 1.5 por cuota)
            tier2_candidates = [m for m in available_models if "1.5-flash" in m]
            if not tier2_candidates:
                tier2_candidates = [m for m in available_models if "flash" in m]
            self.target_critical = tier2_candidates[0] if tier2_candidates else available_models[0]
            
            # 2. Seleccionar Tier 1 (Light - Prioridad Gemma-3 14.4K RPD)
            tier1_candidates = [m for m in available_models if "gemma-3" in m]
            if not tier1_candidates:
                tier1_candidates = [m for m in available_models if "lite" in m or "8b" in m]
            self.target_light = tier1_candidates[0] if tier1_candidates else self.target_critical
            
            # Inicializar modelos
            self.model_light = genai.GenerativeModel(model_name=self.target_light)
            self.model_critical = genai.GenerativeModel(model_name=self.target_critical)
            
            self.system_ready = True
            self.enabled = True
            
            # Re-configurar Buckets para los nuevos modelos detectados
            for tier, model_name in [("light", self.target_light), ("critical", self.target_critical)]:
                config = next((v for k, v in self.MODEL_CONFIGS.items() if k in model_name), self.MODEL_CONFIGS["default"])
                self.buckets[tier]["rpm"] = config["rpm"]
                self.buckets[tier]["rpd_limit"] = config["rpd"]

            # Resetear Rate Limiter y Cache al cambiar de llave
            for tier in ["light", "critical"]:
                self.buckets[tier]["tokens"] = self.buckets[tier]["rpm"]
                self.buckets[tier]["rpd_count"] = 0
                
            self._signal_cache = {}
            
            self.logger.success(f"🔑 Oráculo reconectado con nueva llave.")
            return True
        except Exception as e:
            self.logger.error(f"Error en re-init del Oráculo: {e}")
            return False
