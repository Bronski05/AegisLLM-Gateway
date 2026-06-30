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

logger = get_logger("aegis_gateway")

# Definicje metryk zarejestrowane w domyślnym rejestrze (REGISTRY)
HTTP_REQUESTS_TOTAL = Counter("aegis_http_requests_total", "Total requests", ["method", "endpoint", "http_status"])
HTTP_REQUEST_DURATION_SECONDS = Histogram("aegis_http_request_duration_seconds", "Latency", ["method", "endpoint"])
SHADOW_REQUESTS_TOTAL = Counter("aegis_shadow_requests_total", "Total shadow requests", ["model", "status"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=500, keepalive_expiry=30.0)
    app.state.http_client = httpx.AsyncClient(limits=limits, timeout=60.0)
    
    app.state.redis_client = from_url(settings.REDIS_URL, decode_responses=True)
    app.state.qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
    
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
                raise RuntimeError("Zależności infrastrukturalne nie wystartowały.") from e
            await asyncio.sleep(retry_delay)

    app.state.cache = SemanticCache(
        redis_client=app.state.redis_client,
        qdrant_client=app.state.qdrant_client,
        http_client=app.state.http_client
    )
    await app.state.cache.init_cache_store()
    
    app.state.shadow_router = ShadowRouter(http_client=app.state.http_client, metric_counter=SHADOW_REQUESTS_TOTAL)   
    app.state.security_detector = PromptInjectionDetector()
    
    logger.info("AegisLLM Gateway pomyślnie zainicjalizowany w trybie Gemini-Enterprise.")
    yield
    
    await app.state.qdrant_client.close()
    await app.state.redis_client.close()
    await app.state.http_client.aclose()

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

@app.middleware("http")
async def track_telemetry(request: Request, call_next):
    if request.url.path in ["/metrics", "/healthz"]:
        return await call_next(request)
    method = request.method
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=request.url.path, http_status=str(response.status_code)).inc()
        return response
    except Exception:
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=request.url.path, http_status="500").inc()
        raise
    finally:
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=request.url.path).observe(time.perf_counter() - start_time)

@app.get("/metrics")
async def metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz")
async def health_check(request: Request):
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
    body = await request.json()
    messages = body.get("messages", [])
    
    if not messages:
        return Response(content=json.dumps({"error": "Brak wiadomości"}), status_code=status.HTTP_400_BAD_REQUEST, media_type="application/json")
        
    user_prompt = messages[-1].get("content", "")
    
    # 1. Weryfikacja bezpieczeństwa (Firewall)
    security_detector = request.app.state.security_detector
    if await security_detector.inspect_prompt(user_prompt):
        return Response(
            content=json.dumps({"error": "Security Policy Violation", "message": "Prompt injection blocked."}),
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json"
        )

    # 2. Shadow Routing pod Gemini (Asynchronicznie w tle przez BackgroundTasks)
    shadow_router = request.app.state.shadow_router
    background_tasks.add_task(shadow_router.route_shadow_traffic, body, settings.GEMINI_API_KEY)

    # 3. Semantyczny Cache
    cache = request.app.state.cache
    cached_response = await cache.lookup(user_prompt)
    if cached_response:
        return json.loads(cached_response)

    # Atrapa odpowiedzi (MOCK)
    mock_upstream_response = {
        "choices": [{"message": {"role": "assistant", "content": f"Odpowiedź Gemini na: {user_prompt[:20]}..."}}]
    }
    
    await cache.set(user_prompt, json.dumps(mock_upstream_response), ttl=86400)
    return mock_upstream_response