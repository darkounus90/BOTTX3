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
        keys_env = os.environ.get("GEMINI_API_KEY", "")
        self.api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
        self.current_key_idx = 0
        self.api_key = self.api_keys[0] if self.api_keys else ""
        
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
        self.last_narration = "Esperando diagnóstico inicial..."

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
                # Omitir incompatibles, versiones obsoletas, modelos beta, experimentales y lentos (PRO/ULTRA)
                if any(x in m.lower() for x in ["vision", "embedding", "text-bison", "tts", "robotics", "preview", "experimental", "customtools", "pro", "ultra"]):
                    continue
                # Evitamos poner a Gemma o Lite en la cima principal de la cascada
                if "lite" in m or "gemma" in m:
                    continue
                cands.append(m)
            
            # Ordenar: Queremos que las versiones "3" vayan primero, luego "2.5", luego "flash-latest"
            # Prioridad para modelos Flash rápidos
            def _sort_key(m_name):
                base = 0
                
                if "3.1" in m_name: base += 310
                elif "3.0" in m_name or "-3-" in m_name: base += 300
                elif "2.5" in m_name: base += 250
                elif "2.0" in m_name: base += 200
                elif "1.5" in m_name: base += 150
                return base
                
            cands.sort(key=_sort_key, reverse=True)
            self.cascade_models = cands # Usar TODOS los modelos principales disponibles en lugar de solo 4

            # Anexamos todos los Lite disponibles como Fallback Intermedio (Ej: 3.1-lite, 2.5-lite)
            lite_cands = [m for m in available_models if "lite" in m and "tts" not in m]
            lite_cands.sort(reverse=True)
            for lc in lite_cands: # Añadir absolutamente todos los lites a la cascada
                if lc not in self.cascade_models:
                    self.cascade_models.append(lc)

            # 2. Seleccionar el Fallback Definitivo (Gemma-3 - infinito)
            # Priorizamos versiones balanceadas (4b o 12b) en lugar del 1b
            t1_cands = [m for m in available_models if "gemma-3-4b" in m or "gemma-3-12b" in m]
            if not t1_cands:
                t1_cands = [m for m in available_models if "gemma-3" in m]
            self.target_light = t1_cands[0] if t1_cands else "default-light"

            # 3. Configurar Buckets para la lista final
            num_keys = len(self.api_keys) if self.api_keys else 1
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
                
                if m_name in available_models:
                    self.models_instances[m_name] = genai.GenerativeModel(model_name=m_name)
                
                # Multiplicar los límites por la cantidad de API keys disponibles
                base_rpm = config["rpm"] * num_keys
                base_rpd = config["rpd"] * num_keys
                
                self.buckets[m_name] = {
                    "tokens": base_rpm,
                    "last_refill": time.time(),
                    "rpm": base_rpm,
                    "rpd_count": 0,
                    "rpd_limit": base_rpd
                }
            
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
                # Round-Robin API Keys para distribuir consumo si hay múltiples
                if len(self.api_keys) > 1:
                    self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                    self.api_key = self.api_keys[self.current_key_idx]
                    genai.configure(api_key=self.api_key)

                # Gemma-3 requiere prompts más directos, limpiamos posibles instrucciones conflictivas
                # Generar contenido con timeout de seguridad (30s)
                response = model.generate_content(prompt, request_options={"timeout": 30.0})
                if response and response.text:
                    txt = response.text.strip()
                    # Si no es JSON (es narrativo), guardamos para el dashboard
                    if not txt.startswith("{"):
                        self.last_narration = txt
                    return txt
                return None
            except Exception as e:
                err_str = str(e).lower()
                last_error = str(e)
                if "429" in err_str or "quota" in err_str:
                    if len(self.api_keys) > 1:
                        # Forzar cambio de clave si da error de cuota en una
                        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
                        self.api_key = self.api_keys[self.current_key_idx]
                        genai.configure(api_key=self.api_key)
                        
                    if "retry in" in err_str and len(self.api_keys) <= 1:
                        # Error de RPM largo y no hay otra clave, saltamos directamente de modelo
                        self.logger.warning(f"⏩ Quota excedida en {model.model_name}. Saltando de modelo...")
                        break
                    
                    if attempt >= 1:
                         # Si ya intentamos con las claves disponibles esta vez, salimos para probar otro modelo
                         self.logger.warning(f"⏩ {model.model_name} saturado. Saltando de modelo temporalmente...")
                         break
                         
                    time.sleep(3 * (attempt + 1))
                    continue
                self.logger.error(f"AI Error en {model.model_name}: {e}")
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

        # 3. PREPARAR CONTEXTO AVANZADO Y PROMPT
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

        models_to_try = [m for m in self.cascade_models if m in self.buckets and self.buckets[m]["rpd_count"] < self.buckets[m]["rpd_limit"]]
        models_to_try.append(self.target_light)

        resp_text = None
        model_used = None
        for m_name in models_to_try:
            resp_text = self._call_model(m_name, prompt, urgent=True)
            if resp_text and not resp_text.startswith("ERROR_"):
                model_used = m_name
                break
            self.logger.warning(f"⏩ Modelo {m_name} saturado o con error. Ejecutando salto de Cascada al siguiente nivel...")

        if not resp_text or resp_text.startswith("ERROR_"):
            return {"decision": "APPROVED", "reason": "Quant Bypass (Todos los Modelos IA fallaron)"}

        try:
            clean_text = resp_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            data["decision"] = data.get("decision", "APPROVED").upper()
            
            # Decorar la razón con el modelo que lo aprobó para transparencia del usuario
            base_reason = data.get("reason", "Aprobado por IA")
            clean_model_name = model_used.replace("models/", "") if model_used else "Desconocido"
            data["reason"] = f"{base_reason} [Consultado por: {clean_model_name}]"
            
            self._signal_cache[cache_id] = (candle_key, data)
            return data
        except Exception as e:
            return {"decision": "APPROVED", "reason": f"IA Parsing Error: {e}"}

    def evaluate_exit(self, symbol: str, current_profit_pips: float, order_type: str) -> dict:
        """Consultamos a la IA si es prudente cerrar un trade que está en ganancia (Ahorro de Cuota)."""
        if not self.enabled or not self.system_ready:
            return {"decision": "HOLD", "reason": "Oracle Bypass"}

        # 1. VERIFICAR CACHÉ (Ahorro de cuota por vela de M15)
        now_nyc = datetime.now(ZoneInfo("America/New_York"))
        candle_key = now_nyc.strftime("%Y%m%d%H") + str(now_nyc.minute // 15)
        cache_id = f"EXIT_{symbol}_{order_type}"
        
        if cache_id in self._signal_cache:
            last_candle, last_decision = self._signal_cache[cache_id]
            if last_candle == candle_key:
                return last_decision

        context_data = "Estructura H1/M15 neutral"
        try:
            import MetaTrader5 as mt5
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 5)
            if rates is not None:
                closes = [r['close'] for r in rates]
                trend = "Higher Highs" if closes[-1] > closes[0] else "Lower Lows"
                context_data = f"Trend: {trend} | Last 5 Candles M15: {closes}"
        except: pass

        prompt = (
            f"ERES CIO DE HEDGE FUND (SMC/ICT Professional).\n"
            f"Tenemos una posición {order_type} viva en {symbol} con +{current_profit_pips:.1f} pips de ganancia flotante.\n"
            f"Estructura M15/H1 actual: {context_data}\n\n"
            f"REGLA DE GESTIÓN DE RIESGO:\n"
            f"Decide si cerramos la operación para asegurar la ganancia anticipadamente (CLOSE) o si la tendencia sigue firme y tiene espacio para correr (HOLD).\n"
            f"Si intuyes rechazo de liquidez, soporte o resistencia inminente en contra del trade, asegura.\n"
            f"RESPONDE SOLO JSON: {{'decision':'CLOSE|HOLD', 'reason':'breve motivo'}}"
        )

        # En lugar de usar la Cascada pesada (Gemini), utilizamos a GEMMA-3 directamente para evaluar salidas (Ahorro de API).
        resp_text = self._call_model(self.target_light, prompt, urgent=False)

        if not resp_text or resp_text.startswith("ERROR_"):
            return {"decision": "HOLD", "reason": "Oráculo Gemma cansado, mantenemos regla técnica"}

        try:
            clean_text = resp_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            data["decision"] = data.get("decision", "HOLD").upper()
            
            self._signal_cache[cache_id] = (candle_key, data)
            return data
        except Exception as e:
            return {"decision": "HOLD", "reason": f"Error del Oráculo: {e}"}

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
        return resp if resp and not resp.startswith("ERROR_") else "🏥 Dr. Quant ocupado. Sistema estable en reporte técnico."

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
        if (not resp or resp.startswith("ERROR_")) and model_to_use != self.target_light:
            resp = self._call_model(self.target_light, prompt, urgent=True)
            
        return resp if resp and not resp.startswith("ERROR_") else "⚠️ Oráculo pensando demasiado (Rate Limit). Intenta luego."

    def re_init(self, new_key: str) -> bool:
        """Permite actualizar la API Key en caliente (soporta múltiples separadas por coma)"""
        self.api_keys = [k.strip() for k in new_key.split(",") if k.strip()]
        if not self.api_keys:
            self.api_keys = [""]
        self.current_key_idx = 0
        self.api_key = self.api_keys[0]

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
