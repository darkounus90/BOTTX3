import os
import requests
from datetime import datetime
from utils.logger import BotLogger

class AISentimentAnalyzer:
    """
    🧠 AI Sentiment Analyzer
    Analiza titulares de noticias financieras en tiempo real para determinar
    si el sentimiento es alcista (Bullish), bajista (Bearish) o neutral.
    
    Utiliza el modelo FinBERT (optimizando recursos mediante API o procesamiento ligero).
    """

    def __init__(self, logger: BotLogger):
        self.logger = logger
        # URL de la API gratuita de Inferencia de Hugging Face para FinBERT
        self.api_url = "https://api-inference.huggingface.co/models/ProsusAI/finbert"
        # Obtener token de entorno (si existe)
        self.hf_token = os.environ.get("HUGGINGFACE_TOKEN", "")
        self.headers = {"Authorization": f"Bearer {self.hf_token}"} if self.hf_token else {}
        
        self.logger.info("🧠 Módulo AI Sentiment (FinBERT) Inicializado.")
        if not self.hf_token:
            self.logger.warning("⚠️ No se encontró HUGGINGFACE_TOKEN. Se usará análisis de palabras clave como backup.")

    def evaluate_news_impact(self, title: str, expected: float = None, actual: float = None) -> dict:
        """
        Evalúa el impacto de una noticia usando NLP y contexto de datos.
        Retorna un dict con: {'sentiment': 'BULLISH'|'BEARISH'|'NEUTRAL', 'score': 0-100, 'shock': bool}
        """
        result = {
            "sentiment": "NEUTRAL",
            "score": 50.0,
            "shock": False,
            "raw_text": title
        }

        # 1. EVALUACIÓN DE SORPRESA (SHOCK)
        if expected is not None and actual is not None:
            deviation = abs(actual - expected)
            # Si el valor real se desvía más de un 20% de lo esperado, es un shock
            if expected != 0 and (deviation / abs(expected)) > 0.2:
                result["shock"] = True
                self.logger.info(f"⚡ SHOCK MACROECONÓMICO DETECTADO! Previsto: {expected} | Real: {actual}")

        # 2. ANÁLISIS NLP (Procesamiento de Lenguaje)
        nlp_result = self._analyze_text_finbert(title)
        
        if nlp_result["label"] == "positive":
            result["sentiment"] = "BULLISH"
            result["score"] = nlp_result["score"] * 100
        elif nlp_result["label"] == "negative":
            result["sentiment"] = "BEARISH"
            result["score"] = nlp_result["score"] * 100

        self.logger.info(f"📉 AI Sentimiento: {result['sentiment']} ({result['score']:.1f}%) | Titular: {title}")
        return result

    def _analyze_text_finbert(self, text: str) -> dict:
        """
        Llama al modelo FinBERT. Si falla o no hay token, usa un método ultraligero de backup.
        """
        if self.hf_token:
            try:
                # Intento con finBERT real via API
                response = requests.post(self.api_url, headers=self.headers, json={"inputs": text}, timeout=5)
                if response.status_code == 200:
                    data = response.json()[0]
                    # Retorna la etiqueta con mayor probabilidad (positive, negative, neutral)
                    best_match = max(data, key=lambda x: x['score'])
                    return best_match
            except Exception as e:
                self.logger.error(f"Error conectando a NLP API: {e}")
        
        # BACKUP: Algoritmo de palabras clave (Carga instantánea en el VPS sin internet externo)
        return self._fallback_keyword_analysis(text)

    def _fallback_keyword_analysis(self, text: str) -> dict:
        """Un analizador de sentimiento NLP offline de respaldo."""
        try:
            from textblob import TextBlob
            
            # --- NOVEDAD: CAPA VADER (Excelente para Finanzas) ---
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                vader = SentimentIntensityAnalyzer()
                vader_score = vader.polarity_scores(text)['compound']
                
                if vader_score >= 0.05:
                     return {"label": "positive", "score": min(0.5 + (vader_score / 2), 0.99)}
                elif vader_score <= -0.05:
                     return {"label": "negative", "score": min(0.5 + (abs(vader_score) / 2), 0.99)}
                else:
                     return {"label": "neutral", "score": 0.80}
            except ImportError:
                # Si no hay VADER, caemos a TextBlob (Tercera Capa)
                analysis = TextBlob(text)
                polarity = analysis.sentiment.polarity
                
                if polarity > 0.15:
                    return {"label": "positive", "score": min(0.5 + (polarity / 2), 0.99)}
                elif polarity < -0.15:
                    return {"label": "negative", "score": min(0.5 + (abs(polarity) / 2), 0.99)}
                else:
                    return {"label": "neutral", "score": 0.80}
        except ImportError:
            # Si ni TextBlob ni VADER están instalados, usamos el léxico arcaico (Cuarta Capa)
            text_lower = text.lower()
            bullish_words = ['surge', 'jump', 'rise', 'higher', 'beat', 'growth', 'positive', 'up', 'increase', 'soar', 'bull']
            bearish_words = ['fall', 'drop', 'decline', 'lower', 'miss', 'contract', 'negative', 'down', 'decrease', 'plunge', 'bear']
            
            bull_score = sum(1 for word in bullish_words if word in text_lower)
            bear_score = sum(1 for word in bearish_words if word in text_lower)
            
            if bull_score > bear_score:
                return {"label": "positive", "score": 0.85}
            elif bear_score > bull_score:
                return {"label": "negative", "score": 0.85}
            else:
                return {"label": "neutral", "score": 0.90}

    def should_trade_news(self, sentiment_result: dict, technical_signal: str) -> bool:
        """
        Compara la señal técnica de las EMAs (ej. 'BUY') con el sentimiento de la IA.
        Si la IA dice BULLISH y el técnico dice BUY -> 🟢 TRADE (¡y con más confianza!)
        Si la IA dice BEARISH y el técnico dice BUY -> 🔴 ABORT (Divergencia peligrosa)
        """
        if sentiment_result["sentiment"] == "NEUTRAL":
            return True  # La noticia no tiene peso, operamos el técnico

        if technical_signal == "BUY" and sentiment_result["sentiment"] == "BULLISH":
            self.logger.info("✅ ALINEACIÓN IA + TÉCNICO: Permiso concedido para COMPRAR.")
            return True
            
        if technical_signal == "SELL" and sentiment_result["sentiment"] == "BEARISH":
            self.logger.info("✅ ALINEACIÓN IA + TÉCNICO: Permiso concedido para VENDER.")
            return True

        self.logger.warning(f"🚫 DIVERGENCIA IA: Técnico dice {technical_signal} pero IA lee {sentiment_result['sentiment']}. Evitando entrada falsa.")
        return False
