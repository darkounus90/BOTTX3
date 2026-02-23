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
                    # Usamos flash por velocidad de ejecución en Real Time
                    self.model = genai.GenerativeModel(
                        model_name="gemini-1.5-flash",
                        system_instruction="Eres el Chief Investment Officer (CIO) de un Hedge Fund de alta frecuencia. Tu trabajo es revisar las propuestas algorítmicas de transacciones de Forex. Conoces los conceptos de Smart Money Concepts (SMC), ICT y Price Action dinámico. Analizas el contexto rápido y decides si APROBAR o RECHAZAR la operación. Eres conservador, proteges el capital. Responde SIEMPRE en formato JSON con dos llaves: 'decision' (solo puede ser APPROVED o REJECTED) y 'reason' (explicación breve de 1 línea)."
                    )
                    self.system_ready = True
                    self.logger.success("👁️‍🗨️ LLM ORACLE (Gemini 1.5) Despertó y está Vigilando las transacciones.")
                except Exception as e:
                    self.logger.error(f"Error inicializando Gemini Oracle: {e}")
                    self.enabled = False

    def evaluate_trade(self, symbol: str, signal_type: str, reason: str, adx: float = None) -> dict:
        """
        Envía toda la telemetría del trade propuesto al oráculo de Gemini.
        Returns un dict con la decision.
        """
        if not self.system_ready or not self.enabled:
            # Si el oráculo está apagado o roto, permitir pasar el trade a nivel Quant normal
            return {"decision": "APPROVED", "reason": "Oracle Disabled or Unreachable."}
            
        now = datetime.now()
        prompt = (
            f"PROPUESTA DE TRADE ALGÓRITMICO:\n"
            f"- Símbolo: {symbol}\n"
            f"- Sentido Operativo: {signal_type}\n"
            f"- Gatillo Técnico: {reason}\n"
            f"- Fuerza de Tenencia ADX: {adx if adx else 'N/A'}\n"
            f"- Hora del Servidor: {now.strftime('%H:%M EST')}\n"
            f"¿Apruebas arriesgar el capital del Prop Firm en esta operación ahora mismo basándote en que un Bot básico lo detectó? (Responde en JSON)."
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
                
                if final_decision == "APPROVED":
                    self.logger.success(f"👁️‍🗨️ ORACLE APROBÓ: {final_reason}")
                else:
                    self.logger.warning(f"👁️‍🗨️ ORACLE VETÓ (RECHAZÓ) EL TRADE: {final_reason}")
                    
                return {"decision": final_decision, "reason": final_reason}
                
            except json.JSONDecodeError:
                # Si Gemini responde fuera de formato, ser cautelosos y abortar
                self.logger.error(f"Oracle respondió basura no-JSON: {text}")
                return {"decision": "REJECTED", "reason": "Oracle NLP Parsing Error - Safety Abort"}
                
        except Exception as e:
            self.logger.error(f"Falla de conexión al CIO Gemini: {e}")
            return {"decision": "APPROVED", "reason": "Oracle Network Failure - Quant Override"}
