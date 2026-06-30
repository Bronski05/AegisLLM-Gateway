import asyncio  # <-- Upewnij się, że ten import tu jest
import httpx
from logger import get_logger

logger = get_logger("aegis_shadow_router")

class ShadowRouter:
    def __init__(self, http_client: httpx.AsyncClient, metric_counter):
        self.http = http_client
        self.metric = metric_counter  # Przekazujemy zarejestrowaną metrykę z main.py

    async def route_shadow_traffic(self, body: dict, api_key: str):
        """
        Natywny Asynchroniczny Shadow Routing dla Google Gemini Enterprise Pipeline.
        Wykonuje się w tle (BackgroundTasks) nie obciążając głównego potoku żądania.
        """
        if not api_key:
            logger.warning("Brak klucza GEMINI_API_KEY. Shadow routing pominięty.")
            return
            
        try:
            # Tutaj w przyszłości wejdzie asynchroniczne wywołanie upstreamu:
            # response = await self.http.post("https://generativelanguage.googleapis.com/...", json=body)
            
            # Atrapa asynchronicznego I/O (symulacja zapytania sieciowego)
            await asyncio.sleep(0.001) 
            
            # Podbijamy metrykę przekazaną bezpośrednio z głównego rejestru aplikacji
            self.metric.labels(model="gemini-1.5-flash", status="200").inc()
            
        except Exception as e:
            logger.error(f"Błąd asynchronicznego Shadow Routingu: {e}")
            self.metric.labels(model="gemini-1.5-flash", status="500").inc()