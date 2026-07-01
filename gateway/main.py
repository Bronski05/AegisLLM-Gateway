import asyncio
import time
import json
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, status, BackgroundTasks
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST, REGISTRY

from qdrant_client import AsyncQdrantClient
from redis.asyncio import from_url

from config import settings
from cache import SemanticCache
from routing import ShadowRouter
from security import PromptInjectionDetector
from logger import get_logger


# Logger aplikacyjny (spójny format JSON dla obserwowalności)
logger = get_logger("aegis_gateway")

# =========================
# METRYKI PROMETHEUS
# =========================

# Licznik wszystkich requestów HTTP (podział po metodzie, endpoint i statusie)
HTTP_REQUESTS_TOTAL = Counter(
    "aegis_http_requests_total",
    "Total requests",
    ["method", "endpoint", "http_status"]
)

# Histogram czasu odpowiedzi API (latency observability)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aegis_http_request_duration_seconds",
    "Latency",
    ["method", "endpoint"]
)

# Metryka shadow traffic (testy równoległe / eksperymentalne routingi)
SHADOW_REQUESTS_TOTAL = Counter(
    "aegis_shadow_requests_total",
    "Total shadow requests",
    ["model", "status"]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # =========================
    # INIT INFRASTRUCTURE LAYER
    # =========================

    # HTTP client z limitami połączeń (stabilność under load)
    limits = httpx.Limits(
        max_keepalive_connections=100,
        max_connections=500,
        keepalive_expiry=30.0
    )

    app.state.http_client = httpx.AsyncClient(limits=limits, timeout=60.0)

    # Klienci infrastruktury (Redis + Qdrant)
    app.state.redis_client = from_url(settings.REDIS_URL, decode_responses=True)
    app.state.qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)

    # Retry loop – gwarancja gotowości zależności przed startem API
    max_retries = 10
    retry_delay = 2.0

    for attempt in range(1, max_retries + 1):
        try:
            await app.state.redis_client.ping()
            await app.state.qdrant_client.get_collections()
            break

        except Exception as e:
            if attempt == max_retries:
                logger.critical(f"Infrastruktura krytyczna leży: {e}")
                raise RuntimeError(
                    "Zależności infrastrukturalne nie wystartowały."
                ) from e

            await asyncio.sleep(retry_delay)

    # =========================
    # APP COMPONENTS INIT
    # =========================

    # Warstwa cache semantycznego (Redis + Qdrant)
    app.state.cache = SemanticCache(
        redis_client=app.state.redis_client,
        qdrant_client=app.state.qdrant_client,
        http_client=app.state.http_client
    )
    await app.state.cache.init_cache_store()

    # Shadow routing (testowanie alternatywnego modelu bez wpływu na user flow)
    app.state.shadow_router = ShadowRouter(
        http_client=app.state.http_client,
        metric_counter=SHADOW_REQUESTS_TOTAL
    )

    # Detektor prompt injection (warstwa security / firewall LLM)
    app.state.security_detector = PromptInjectionDetector()

    logger.info("AegisLLM Gateway pomyślnie zainicjalizowany w trybie Gemini-Enterprise.")

    yield

    # =========================
    # SHUTDOWN CLEANUP
    # =========================
    await app.state.qdrant_client.close()
    await app.state.redis_client.close()
    await app.state.http_client.aclose()


# FastAPI application entrypoint
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


@app.middleware("http")
async def track_telemetry(request: Request, call_next):
    # Middleware telemetryczne – pomiar ruchu i latency
    if request.url.path in ["/metrics", "/healthz"]:
        return await call_next(request)

    method = request.method
    start_time = time.perf_counter()

    try:
        response = await call_next(request)

        # Zapis metryk sukcesu / błędów HTTP
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=request.url.path,
            http_status=str(response.status_code)
        ).inc()

        return response

    except Exception:
        # Rejestracja błędu 500 w metrykach
        HTTP_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=request.url.path,
            http_status="500"
        ).inc()
        raise

    finally:
        # Pomiar czasu odpowiedzi niezależnie od wyniku requestu
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method,
            endpoint=request.url.path
        ).observe(time.perf_counter() - start_time)


@app.get("/metrics")
async def metrics():
    # Endpoint Prometheus scrape
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def health_check(request: Request):
    # Healthcheck – weryfikacja zależności infrastrukturalnych
    health_status = {"status": "healthy", "dependencies": {}}

    try:
        await request.app.state.redis_client.ping()
        health_status["dependencies"]["redis"] = "UP"
    except Exception:
        health_status["dependencies"]["redis"] = "DOWN"

    try:
        await request.app.state.qdrant_client.get_collections()
        health_status["dependencies"]["qdrant"] = "UP"
    except Exception:
        health_status["dependencies"]["qdrant"] = "DOWN"

    return health_status


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request, background_tasks: BackgroundTasks):
    # Główne API gateway – proxy / orchestration warstwa LLM

    body = await request.json()
    messages = body.get("messages", [])

    # Walidacja wejścia (brak payloadu)
    if not messages:
        return Response(
            content=json.dumps({"error": "Brak wiadomości"}),
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

    user_prompt = messages[-1].get("content", "")

    # =========================
    # 1. SECURITY LAYER (LLM firewall)
    # =========================
    security_detector = request.app.state.security_detector

    if await security_detector.inspect_prompt(user_prompt):
        return Response(
            content=json.dumps({
                "error": "Security Policy Violation",
                "message": "Prompt injection blocked."
            }),
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

    # =========================
    # 2. SHADOW ROUTING (async observability / testing)
    # =========================
    shadow_router = request.app.state.shadow_router
    background_tasks.add_task(
        shadow_router.route_shadow_traffic,
        body,
        settings.GEMINI_API_KEY
    )

    # =========================
    # 3. SEMANTIC CACHE (Redis + Qdrant)
    # =========================
    cache = request.app.state.cache
    cached_response = await cache.lookup(user_prompt)

    if cached_response:
        return json.loads(cached_response)

    # =========================
    # 4. MOCK UPSTREAM (LLM placeholder)
    # =========================
    mock_upstream_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"Odpowiedź Gemini na: {user_prompt[:20]}..."
                }
            }
        ]
    }

    # Zapis do cache (TTL 24h)
    await cache.set(
        user_prompt,
        json.dumps(mock_upstream_response),
        ttl=86400
    )

    return mock_upstream_response