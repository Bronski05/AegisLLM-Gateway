import asyncio
import httpx
from logger import get_logger


# Logger dla warstwy shadow routing (eksperymentalny traffic / observability)
logger = get_logger("aegis_shadow_router")


class ShadowRouter:
    def __init__(self, http_client: httpx.AsyncClient, metric_counter):
        # Klient HTTP współdzielony z główną aplikacją (brak overheadu tworzenia połączeń)
        self.http = http_client

        # Metryka Prometheus przekazana z main.py (centralny rejestr obserwowalności)
        self.metric = metric_counter

    async def route_shadow_traffic(self, body: dict, api_key: str):
        """
        Shadow routing – równoległe wysyłanie requestów do alternatywnego modelu.
        Nie wpływa na odpowiedź użytkownika (fire-and-forget background task).
        """

        # Brak klucza API → brak możliwości wykonania shadow requestów
        if not api_key:
            logger.warning("Brak klucza GEMINI_API_KEY. Shadow routing pominięty.")
            return

        try:
            # ==========================================
            # FUTURE INTEGRATION LAYER (upstream LLM)
            # ==========================================
            # Docelowo tutaj będzie realny request do Gemini API:
            # response = await self.http.post(
            #     "https://generativelanguage.googleapis.com/...",
            #     json=body
            # )

            # Symulacja I/O (udawane opóźnienie sieciowe)
            await asyncio.sleep(0.001)

            # Rejestracja metryki shadow traffic (model + status)
            self.metric.labels(
                model="gemini-1.5-flash",
                status="200"
            ).inc()

        except Exception as e:
            # Log błędu shadow pipeline (nie wpływa na main request flow)
            logger.error(f"Błąd asynchronicznego Shadow Routingu: {e}")

            # Rejestracja failure w metrykach obserwowalności
            self.metric.labels(
                model="gemini-1.5-flash",
                status="500"
            ).inc()