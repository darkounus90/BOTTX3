"""
📰 News Filter - Filtro de Noticias Económicas
================================================
Evita operar durante noticias de alto impacto que causan
volatilidad extrema e impredecible.

Fuente: ForexFactory / Investing.com calendar API
"""

import requests
from datetime import datetime, timedelta
from config.settings import BotConfig
from utils.logger import BotLogger
from core.ai_sentiment import AISentimentAnalyzer


class NewsFilter:
    """
    Filtra momentos de noticias económicas de alto impacto.

    - No abre posiciones 30 minutos antes de una noticia HIGH impact
    - No abre posiciones 15 minutos después de una noticia HIGH impact
    - Monitorea: NFP, FOMC, CPI, GDP, Interest Rate Decisions
    """

    # Noticias de alto impacto clave (USD-related)
    HIGH_IMPACT_KEYWORDS = [
        "Non-Farm",
        "NFP",
        "FOMC",
        "Federal Funds Rate",
        "Interest Rate Decision",
        "CPI",
        "Consumer Price Index",
        "GDP",
        "Gross Domestic Product",
        "Retail Sales",
        "Unemployment",
        "PMI",
        "ECB",
        "BOE",
        "BOJ",
    ]

    # Currencies que afectan a cada noticia
    CURRENCY_MAP = {
        "USD": ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF"],
        "EUR": ["EURUSD", "EURGBP", "EURJPY"],
        "GBP": ["GBPUSD", "EURGBP", "GBPJPY"],
        "JPY": ["USDJPY", "EURJPY", "GBPJPY"],
        "AUD": ["AUDUSD", "AUDNZD"],
        "CAD": ["USDCAD"],
    }

    def __init__(self, logger: BotLogger):
        self.logger = logger
        self.enabled = BotConfig.NEWS_FILTER_ENABLED
        self.avoid_before = BotConfig.NEWS_AVOID_MINUTES_BEFORE
        self.avoid_after = BotConfig.NEWS_AVOID_MINUTES_AFTER
        
        self.ai_analyzer = AISentimentAnalyzer(logger=self.logger)

        # Cache de noticias del día
        self._cached_events: list[dict] = []
        self._cache_date: str = ""

        if self.enabled:
            self.logger.info(
                f"📰 News Filter activado | "
                f"Antes: {self.avoid_before}min | Después: {self.avoid_after}min"
            )

    def is_safe_to_trade(self, symbol: str = "EURUSD", technical_signal: str = None) -> bool:
        """
        Verifica si es seguro operar el símbolo dado basándose en calendario e IA.

        Returns:
            True si no hay noticias de alto impacto cercanas, o si la IA confirma la entrada.
        """
        if not self.enabled:
            return True

        events = self._get_todays_events()
        if not events:
            return True

        now = datetime.now()

        for event in events:
            # Verificar si la noticia afecta al símbolo
            if not self._event_affects_symbol(event, symbol):
                continue

            event_time = event.get("time")
            if event_time is None:
                continue

            # Calcular ventana de exclusión
            window_start = event_time - timedelta(minutes=self.avoid_before)
            window_end = event_time + timedelta(minutes=self.avoid_after)

            if window_start <= now <= window_end:
                time_to_event = (event_time - now).total_seconds() / 60

                if technical_signal:
                    # IA interviene para decidir si ignoramos la regla de "no operar"
                    forecast = event.get('forecast')
                    previous = event.get('previous')
                    
                    try:
                        expected_val = float(str(forecast).replace('K', '000').replace('M', '000000').replace('%', '')) if forecast else None
                        actual_val = float(str(previous).replace('K', '000').replace('M', '000000').replace('%', '')) if previous else None
                    except ValueError:
                        expected_val, actual_val = None, None

                    sentiment_result = self.ai_analyzer.evaluate_news_impact(
                        title=event.get('title', 'Unknown'),
                        expected=expected_val,
                        actual=actual_val
                    )
                    
                    is_aligned = self.ai_analyzer.should_trade_news(sentiment_result, technical_signal)
                    
                    if is_aligned:
                        if time_to_event > 0:
                            self.logger.warning(f"🚀 IA ALINEADA: Operando pre-noticia ({time_to_event:.0f}m) | {symbol}")
                        else:
                            self.logger.warning(f"🚀 IA ALINEADA: Operando post-noticia ({abs(time_to_event):.0f}m) | {symbol}")
                        return True
                    else:
                        if time_to_event > 0:
                            self.logger.warning(
                                f"🚫 DIVERGENCIA IA/NOTICIA en {time_to_event:.0f} min | "
                                f"No operar {symbol}"
                            )
                        else:
                            self.logger.warning(
                                f"🚫 DIVERGENCIA IA/NOTICIA hace {abs(time_to_event):.0f} min | "
                                f"Esperando post-noticia"
                            )
                        return False

                # Comportamiento original si no hay señal técnica (ej. llamado desde risk manager)
                if time_to_event > 0:
                    self.logger.warning(
                        f"📰 NOTICIA en {time_to_event:.0f} min: "
                        f"{event.get('title', 'Unknown')} | "
                        f"Impacto: HIGH | No operar {symbol}"
                    )
                else:
                    self.logger.warning(
                        f"📰 NOTICIA hace {abs(time_to_event):.0f} min: "
                        f"{event.get('title', 'Unknown')} | "
                        f"Esperando {self.avoid_after}min post-noticia"
                    )

                return False

        return True

    def _get_todays_events(self) -> list[dict]:
        """
        Obtiene los eventos económicos del día.
        Usa cache para no hacer requests cada iteración.
        """
        today = datetime.now().strftime("%Y-%m-%d")

        # Usar cache si es del mismo día
        if self._cache_date == today and self._cached_events:
            return self._cached_events

        try:
            events = self._fetch_events_from_api()
            self._cached_events = events
            self._cache_date = today
            self.logger.info(f"📰 {len(events)} eventos económicos detectados hoy")
            return events

        except Exception as e:
            self.logger.warning(f"📰 No se pudieron obtener eventos: {e}")
            # Si falla la API, usar el schedule estático de noticias clave
            return self._get_static_schedule()

    def _fetch_events_from_api(self) -> list[dict]:
        """
        Intenta obtener eventos del calendario económico.
        Usa la API pública de noticias económicas.
        """
        try:
            # Intentar con ForexFactory/Investing.com calendario
            # Como backup, usamos una API gratuita
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                return []

            data = response.json()
            events = []
            today = datetime.now().strftime("%Y-%m-%d")

            for item in data:
                event_date = item.get("date", "")
                if not event_date.startswith(today):
                    continue

                impact = item.get("impact", "").lower()
                if impact != "high":
                    continue

                try:
                    event_time = datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S%z")
                    # Convertir a hora local real del servidor antes de quitarle el timezone
                    event_time = event_time.astimezone().replace(tzinfo=None)
                except (ValueError, TypeError):
                    continue

                events.append({
                    "title": item.get("title", "Unknown Event"),
                    "currency": item.get("country", "USD"),
                    "impact": "HIGH",
                    "time": event_time,
                    "forecast": item.get("forecast", ""),
                    "previous": item.get("previous", ""),
                })

            return events

        except Exception:
            return []

    def _get_static_schedule(self) -> list[dict]:
        """
        Schedule estático de noticias recurrentes importantes.
        Usado como fallback si la API no responde.
        """
        now = datetime.now()
        events = []

        # NFP: primer viernes de cada mes a las 8:30 AM EST
        if now.weekday() == 4 and now.day <= 7:
            nfp_time = now.replace(hour=8, minute=30, second=0, microsecond=0)
            events.append({
                "title": "Non-Farm Payrolls (NFP)",
                "currency": "USD",
                "impact": "HIGH",
                "time": nfp_time,
            })

        # FOMC: tipicamente ~2 PM EST (8 reuniones al año)
        # CPI: ~8:30 AM EST, alrededor del día 10-14 de cada mes

        return events

    def _event_affects_symbol(self, event: dict, symbol: str) -> bool:
        """Verifica si un evento económico afecta al símbolo dado"""
        currency = event.get("currency", "").upper()

        affected_symbols = self.CURRENCY_MAP.get(currency, [])

        # Si el símbolo está en la lista de afectados
        if symbol in affected_symbols:
            return True

        # Si la moneda es parte del par
        if currency in symbol:
            return True

        return False

    def get_upcoming_events(self, hours_ahead: int = 4) -> list[dict]:
        """Retorna los eventos de las próximas N horas"""
        events = self._get_todays_events()
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)

        upcoming = [
            e for e in events
            if e.get("time") and now <= e["time"] <= cutoff
        ]

        return upcoming
