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
from datetime import datetime
try:
    import google.generativeai as genai
except ImportError:
    genai = None

from utils.logger import BotLogger
from config.settings import BotConfig

class GeminiOracle:
    """
    Motor de Conciencia Institucional impulsado por Google Gemini.
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.enabled = BotConfig.ORACLE_ENABLED
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        
        self.system_ready = False
        
        if self.enabled:
            if not self.api_key or genai is None:
                self.logger.warning("⚠️ Oracle Engine Activado pero falta GEMINI_API_KEY o 'google-generativeai'. El Bot operará Modo Quant puro.")
                self.enabled = False
            else:
                try:
                    genai.configure(api_key=self.api_key)
                    
                    # Auto-detector de modelo compatible (Anti error 404 API v1beta)
                    target_model = "gemini-1.5-flash-latest" # Fallback por defecto
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            name = m.name.replace("models/", "")
                            # Preferir flash o pro si está en los disponibles
                            if 'flash' in name:
                                target_model = name
                                break
                            elif 'pro' in name:
                                target_model = name
                                
                    self.model = genai.GenerativeModel(model_name=target_model)
                    self.system_ready = True
                    self.logger.success(f"👁️‍🗨️ LLM ORACLE ({target_model}) Despertó y está Vigilando.")
                except Exception as e:
                    self.logger.error(f"Error inicializando Gemini Oracle: {e}")
                    self.enabled = False

    def evaluate_trade(self, symbol: str, signal_type: str, reason: str, adx: float = None) -> dict:
        """
        Envía telemetría enriquecida (Multi-Timeframe) al Oráculo.
        Descarga volatilidad en vivo para que Gemini decida con contexto real SMC.
        """
        if not self.system_ready or not self.enabled:
            return {"decision": "APPROVED", "reason": "Oracle Disabled or Unreachable."}
            
        now = datetime.now()
        
        # ─── EXTRAER CONTEXTO MULTI-TIMEFRAME (MTF) RÁPIDO ───
        context_data = "No data"
        try:
            import MetaTrader5 as mt5
            import pandas as pd
            # M15 Context
            m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 5)
            if m15_rates is not None and len(m15_rates) > 0:
                m15_df = pd.DataFrame(m15_rates)
                m15_trend = "BULLISH" if m15_df.iloc[-1]['close'] > m15_df.iloc[0]['open'] else "BEARISH"
                
            # H1 Context
            h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 3)
            if h1_rates is not None and len(h1_rates) > 0:
                h1_df = pd.DataFrame(h1_rates)
                h1_trend = "BULLISH" if h1_df.iloc[-1]['close'] > h1_df.iloc[0]['open'] else "BEARISH"
                
            context_data = f"M15 Short Trend: {m15_trend} | H1 Macro Trend: {h1_trend}"
        except Exception as e:
            self.logger.warning(f"No se pudo inyectar MTF context a Gemini: {e}")
        
        prompt = (
            f"ERES EL CHIEF INVESTMENT OFFICER (CIO) DE UN HEDGE FUND QUANT. Eres estricto, aplicas Smart Money Concepts (SMC) y proteges el capital al máximo.\n\n"
            f"PROPUESTA DE TRADE ALGÓRITMICO (INSTITUCIONAL):\n"
            f"- Símbolo: {symbol}\n"
            f"- Sentido Operativo: {signal_type}\n"
            f"- Contexto Gráfico MTF en Vivo: {context_data}\n"
            f"- Fuerza de Tenencia ADX: {adx if adx else 'N/A'}\n"
            f"- Gatillo Técnico: {reason}\n"
            f"- Hora del Servidor: {now.strftime('%H:%M EST')}\n\n"
            f"¿Apruebas arriesgar capital institucional en este trade basándote en la alineación del contexto MTF y conceptos SMC actuales? Rechaza si M15 contradice macro H1 peligrosamente o estás sobre un posible Liquidity Grab.\n"
            f"(Responde SOLAMENTE un objeto JSON puro con 'decision'='APPROVED|REJECTED', 'reason'='Motivo en 10 palabras', y 'confidence'=número del 0 al 100 indicando probabilidad real de éxito)."
        )
        
        self.logger.info(f"🧠 Consultando CIO Gemini para revisar el trade {signal_type} en {symbol}...")
        
        try:
            # Generar respuesta
            response = self.model.generate_content(prompt)
            text = response.text
            
            # Limpiar markdown de código para leer el JSON puro
            if text.startswith("```json"):
                text = text.replace("```json\n", "").replace("\n```", "").strip()
            elif text.startswith("```"):
                 text = text.replace("```\n", "").replace("\n```", "").strip()
                 
            # Parsear decision
            try:
                decision_data = json.loads(text)
                final_decision = decision_data.get("decision", "APPROVED").upper()
                final_reason = decision_data.get("reason", "No reason provided")
                confidence = float(decision_data.get("confidence", 50.0))
                
                if final_decision == "APPROVED":
                    self.logger.success(f"👁️‍🗨️ ORACLE APROBÓ ({confidence}% conf.): {final_reason}")
                else:
                    self.logger.warning(f"👁️‍🗨️ ORACLE VETÓ ({confidence}% conf.): {final_reason}")
                    
                return {"decision": final_decision, "reason": final_reason, "confidence": confidence}
                
            except json.JSONDecodeError:
                # Si Gemini responde fuera de formato, ser cautelosos y abortar
                self.logger.error(f"Oracle respondió basura no-JSON: {text}")
                return {"decision": "REJECTED", "reason": "Oracle NLP Parsing Error - Safety Abort"}
                
        except Exception as e:
            self.logger.error(f"Falla de conexión al CIO Gemini: {e}")
            return {"decision": "APPROVED", "reason": "Oracle Network Failure - Quant Override"}

    def ask_oracle(self, question: str) -> str:
        """
        Permite hacer consultas generales o análisis de situación al Oráculo vía Telegram.
        """
        if not self.system_ready or not self.enabled:
            return "⚠️ Oráculo Desconectado o API Key faltante."
            
        prompt = (
            f"ERES EL CHIEF INVESTMENT OFFICER (CIO) AI DEL TX3 PRO BOT.\n"
            f"El usuario (dueño de la cuenta) te pregunta lo siguiente:\n"
            f"\"{question}\"\n\n"
            f"Responde de forma concisa, analítica, profesional y directa. Eres un experto en Smart Money Concepts (SMC). Usa formato Markdown para Telegram (negritas '*', sin HTML, usa emojis). Máximo 2 párrafos."
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            self.logger.error(f"Error consultando al Oráculo en modo libre: {e}")
            return f"❌ Oráculo en corto circuito: {e}"
