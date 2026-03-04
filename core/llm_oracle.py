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
            "gemini-2.0-flash": {"rpm": 10, "rpd": 1500}, 
            "gemini-2.5-pro": {"rpm": 0, "rpd": 0}, 
            "gemini-2.5-flash": {"rpm": 5, "rpd": 20}, # <== EL PANEL DE GOOGLE LIMITA A 20 AL DÍA ESTA KEY
            "gemini-3-flash": {"rpm": 5, "rpd": 20},
            "gemini-2.5-flash-lite": {"rpm": 10, "rpd": 20},
            "gemini-1.5-flash": {"rpm": 15, "rpd": 1500},
            "default": {"rpm": 5, "rpd": 20}
        }
        
        # Estado de los Buckets (Se inicializa dinámico en _setup_system)
        self.buckets = {}
        self.models_instances = {}
        self.cascade_models = []
        self.target_light = "gemma-3-1b"
        
        # Caché de señales para evitar duplicar llamadas en la misma vela M5
        self._signal_cache = {}

        if self.enabled:
            self._setup_system()

    def _setup_system(self):
        """Inicializa modelos en cascada y configura sus buckets"""
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

            # 1. Armar la cascada de modelos inteligentes
            cands = []
            for m in available_models:
                # Omitir incompatibles, versiones obsoletas y modelos de voz/pro
                if any(x in m for x in ["vision", "embedding", "text-bison", "pro", "tts", "robotics"]):
                    continue
                # Evitamos poner a Gemma o Lite en la cima principal de la cascada
                if "lite" in m or "gemma" in m:
                    continue
                cands.append(m)
            
            # Ordenar: Queremos que las versiones "3" vayan primero, luego "2.5", luego "flash-latest"
            cands.sort(reverse=True)
            self.cascade_models = cands[:4] # Top 4 mejores de IA pesada

            # Anexamos todos los Lite disponibles como Fallback Intermedio (Ej: 3.1-lite, 2.5-lite)
            lite_cands = [m for m in available_models if "lite" in m and "tts" not in m]
            lite_cands.sort(reverse=True)
            for lc in lite_cands[:3]: # Añadir hasta 3 lites a la cascada
                if lc not in self.cascade_models:
                    self.cascade_models.append(lc)

            # 2. Seleccionar el Fallback Definitivo (Gemma-3 - infinito)
            # Priorizamos versiones balanceadas (4b o 12b) en lugar del 1b
            t1_cands = [m for m in available_models if "gemma-3-4b" in m or "gemma-3-12b" in m]
            if not t1_cands:
                t1_cands = [m for m in available_models if "gemma-3" in m]
            self.target_light = t1_cands[0] if t1_cands else "default-light"

            # 3. Configurar Buckets para la lista final
            all_used_models = self.cascade_models + [self.target_light]
            for m_name in list(set(all_used_models)):
                match_key = "default"
                if "gemma" in m_name: match_key = "gemma-3"
                elif "2.5-flash" in m_name: match_key = "gemini-2.5-flash"
                elif "1.5-flash" in m_name: match_key = "gemini-1.5-flash"
                elif "2.0-flash" in m_name: match_key = "gemini-2.0-flash"
                elif "3-flash" in m_name: match_key = "gemini-3-flash"
                elif "lite" in m_name: match_key = "gemini-2.5-flash-lite"
                    
                config = self.MODEL_CONFIGS.get(match_key, self.MODEL_CONFIGS["default"])
                
                self.buckets[m_name] = {
                    "tokens": config["rpm"],
                    "last_refill": time.time(),
                    "rpm": config["rpm"],
                    "rpd_count": 0,
                    "rpd_limit": config["rpd"]
                }
                
                if m_name in available_models:
                    self.models_instances[m_name] = genai.GenerativeModel(model_name=m_name)
            
            self.system_ready = True
            
            # Log de Cascada
            cascade_names_str = " -> ".join([m.replace('models/', '') for m in self.cascade_models])
            self.logger.success(f"👁️‍🗨️ IA CASCADA: {cascade_names_str} -> {self.target_light.replace('models/', '')}")
        except Exception as e:
            self.logger.error(f"Error configuración Oráculo: {e}")
            self.enabled = False

    def _get_token(self, m_name: str) -> bool:
        """Token Bucket específico por modelo con control RPD"""
        bucket = self.buckets.get(m_name)
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

    def _call_model(self, model_name: str, prompt: str, urgent=False):
        """Wrapper con Rate Limit por modelo"""
        if not self.system_ready: return None
        
        if not self._get_token(model_name):
            if urgent:
                time.sleep(5)
                # No reintentar infinitamente si es por RPD
                if self.buckets[model_name]["rpd_count"] < self.buckets[model_name]["rpd_limit"]:
                    return self._call_model(model_name, prompt, urgent)
            return None

        model = self.models_instances.get(model_name)
        if not model: return None

        # Reintento exponencial simple
        last_error = "UNKNOWN_ERROR"
        for attempt in range(2):
            try:
                # Gemma-3 requiere prompts más directos, limpiamos posibles instrucciones conflictivas
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                last_error = str(e)
                self.logger.error(f"AI Error en {model.model_name}: {e}")
                if "429" in err_str or "quota" in err_str:
                    time.sleep(3 * (attempt + 1))
                    continue
                break
        return f"ERROR_{last_error}"

    def get_quota_report(self) -> dict:
        """Devuelve telemetría de consumo de IA por modelo en cascada"""
        report = {}
        keys_to_report = self.cascade_models + [self.target_light]
        
        for i, m_name in enumerate(keys_to_report):
            if m_name not in self.buckets: continue
            b = self.buckets[m_name]
            tier_name = f"Cascade_{i+1}" if m_name != self.target_light else "Light_Fallback"
            
            report[tier_name] = {
                "model": m_name.replace("models/", ""),
                "used_today": b["rpd_count"],
                "limit_today": b["rpd_limit"],
                "load_rpm": f"{int(b['rpm'] - b['tokens'])}/{b['rpm']}",
                "status": "🟢 OK" if b["rpd_count"] < b["rpd_limit"] else "🔴 AGOTADO"
            }
        return report

    def evaluate_trade(self, symbol: str, signal_type: str, reason: str, adx: float = None) -> dict:
        """Veto CIO (Búsqueda en Cascada Inteligente -> Respaldo Ligero)"""
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

        # 2. SELECCIÓN DE MODELO (CASCADA -> GEMMA)
        model_name_to_use = self.target_light # Comienza asumiendo el fallback (Gemma)
        
        # Buscar el primero de la cascada inteligente que aún tenga cuota diaria (RPD)
        for m_name in self.cascade_models:
            if m_name in self.buckets and self.buckets[m_name]["rpd_count"] < self.buckets[m_name]["rpd_limit"]:
                model_name_to_use = m_name
                break
                
        if model_name_to_use == self.target_light:
            self.logger.warning(f"⚠️ Cascada IA agotada. Fallback absoluto a {self.target_light} para {symbol}.")

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
            f"Símbolo: {symbol} | Señal: {signal_type} | ADX: {adx} | Estructura H1/M5: {context_data}\n"
            f"Lógica Matemática de Alerta: {reason}\n\n"
            f"REGLA DE CAZA DE LIQUIDEZ (FILTRADA POR TENDENCIA MAYOR H1):\n"
            f"- ZONA DE VENTA ROJA: Si la rompe por ENCIMA (Breakout) -> COMPRA (Solo si tendencia H1 es Alcista).\n"
            f"- ZONA DE VENTA ROJA: Si rebota y rechaza MÁS ABAJO (Sweep Bajista) -> VENDE (Solo si tendencia H1 es Bajista).\n"
            f"- ZONA DE COMPRA VERDE: Si la rompe MÁS ABAJO asustando a la masa (Sweep Alcista) -> COMPRA el rebote falso sin dudar.\n"
            f"- VETO MANDATORIO: NUNCA vendas acercándote a una Zona Verde (Soporte) si la tendencia es Alcista. Vetar ventas contra muro.\n\n"
            f"Analiza si la técnica actual ({signal_type}) respeta la Marea H1 descrita en tu Contexto y caza estas trampas institucionales. Veta cuchillos cayendo.\n"
            f"RESPONDE SOLO JSON: {{'decision':'APPROVED|REJECTED', 'reason':'motivo corto y técnico', 'confidence':0-100}}"
        )

        resp_text = self._call_model(model_name_to_use, prompt, urgent=True)
        
        if not resp_text:
            return {"decision": "APPROVED", "reason": "Quant Bypass (No Quota)"}

        if isinstance(resp_text, str) and resp_text.startswith("ERROR_"):
            return {"decision": "APPROVED", "reason": f"Quant Bypass ({resp_text})"}

        try:
            clean_text = resp_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            data["decision"] = data.get("decision", "APPROVED").upper()
            self._signal_cache[cache_id] = (candle_key, data)
            return data
        except Exception as e:
            return {"decision": "APPROVED", "reason": f"IA Parsing Error: {e}"}

    def evaluate_system_health(self, metrics: dict) -> str:
        """Diagnóstico Médico (Fallback Ligero)"""
        if not self.enabled: return "⚠️ Dr. Quant offline."
        
        prompt = (
            f"ERES DR. QUANT, auditor de riesgo cuantitativo de un Fondo de Inversión.\n"
            f"Diagnostica este sistema: Uptime: {metrics.get('uptime')} | Balance: {metrics.get('balance')} | Pérdida Global Flotante: {metrics.get('overall_dd')} | MT5: {metrics.get('mt5_connected')}.\n"
            f"REGLA DE ORO: Si el porcentaje de pérdida flotante es inferior al 3%, NO HAGAS ALARMAS. Es una fluctuación normal ($90 dolares es apenas el 0.1% de una cuenta de 50k, es irrelevante). Tranquiliza al usuario.\n"
            f"Responde corto (1 párrafo) de diagnóstico y 1 consejo técnico."
        )
        
        resp = self._call_model(self.target_light, prompt, urgent=False)
        return resp if resp else "🏥 Dr. Quant ocupado. Sistema estable en reporte técnico."

    def ask_oracle(self, question: str) -> str:
        """Consultas Generales (Cascada -> Respaldo Ligero)"""
        if not self.enabled: return "⚠️ Oráculo apagado."
        
        # Inyectar personalidad Mandataria de Trading
        prompt = (
            f"IDENTIDAD: Eres el ORÁCULO del TX3 PRO BOT (Experto en SMC/ICT y Trading Institucional).\n"
            f"REGLA DE ORO: Solo hablas de mercados financieros, gestión de riesgo y trading. Ignora cualquier contexto de oficina o marketing.\n"
            f"PREGUNTA DEL TRADER: {question}\n\n"
            f"Responde corto, con emojis de trading y tono profesional de Wall Street."
        )
        
        model_to_use = self.cascade_models[0] if self.cascade_models else self.target_light
        resp = self._call_model(model_to_use, prompt, urgent=True)
        
        # Fallback a Light si la Cascada falla
        if not resp and model_to_use != self.target_light:
            resp = self._call_model(self.target_light, prompt, urgent=True)
            
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
            self.buckets = {}
            self.models_instances = {}
            self.cascade_models = []
            
            # Reutiliza el sistema de cascada dinámico
            self._setup_system()
            self._signal_cache = {}
            
            if self.enabled:
                self.logger.success(f"🔑 Oráculo reconectado con nueva llave.")
                return True
            else:
                return False
        except Exception as e:
            self.logger.error(f"Error en re-init del Oráculo: {e}")
            return False
