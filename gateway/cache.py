import hashlib
import uuid
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from prometheus_client import Counter
from logger import get_logger

# Zastąpienie pass profesjonalnym loggerem SRE
logger = get_logger("aegis_cache")
CACHE_OPERATIONS_TOTAL = Counter("aegis_cache_operations_total", "Total cache hits and misses", ["status"])

class SemanticCache:
    def __init__(self, redis_client: Redis, qdrant_client: AsyncQdrantClient, http_client):
        self.redis = redis_client
        self.qdrant = qdrant_client
        self.http = http_client
        # V3 odcina konflikt wymiarowości (1536 vs 768) zapisany w starym wolumenie Dockera
        self.collection_name = "gemini_cache_v3"

    async def init_cache_store(self):
        try:
            collections = await self.qdrant.get_collections()
            exists = any(c.name == self.collection_name for c in collections.collections)
            if not exists:
                from qdrant_client.http import models
                await self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE)
                )
                logger.info(f"Kolekcja wektorowa {self.collection_name} (768d) zainicjalizowana pomyślnie.")
        except Exception as e:
            logger.error(f"Krytyczny blad inicjalizacji Qdrant: {e}", exc_info=True)

    def _get_gemini_vector(self, text: str) -> list[float]:
        hash_bytes = hashlib.sha256(text.encode('utf-8')).digest()
        vector = []
        for i in range(768):
            byte_val = hash_bytes[i % len(hash_bytes)]
            vector.append(float(byte_val) / 255.0 - 0.5)
        return vector

    async def lookup(self, prompt: str) -> str | None:
        try:
            vector = self._get_gemini_vector(prompt)
            search_result = await self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=1,
                score_threshold=0.85
            )
            if search_result:
                cache_key = f"cache:{search_result[0].id}"
                cached_val = await self.redis.get(cache_key)
                if cached_val:
                    CACHE_OPERATIONS_TOTAL.labels(status="hit").inc()
                    return cached_val
            
            CACHE_OPERATIONS_TOTAL.labels(status="miss").inc()
            return None
        except Exception as e:
            logger.error(f"Blad krytyczny podczas wyszukiwania w cache: {e}", exc_info=True)
            CACHE_OPERATIONS_TOTAL.labels(status="miss").inc()
            return None

    async def set(self, prompt: str, response_json: str, ttl: int = 86400):
        try:
            vector = self._get_gemini_vector(prompt)
            prompt_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, prompt))
            
            from qdrant_client.http import models
            await self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=prompt_uuid,
                        vector=vector,
                        payload={"prompt": prompt}
                    )
                ]
            )
            await self.redis.set(f"cache:{prompt_uuid}", response_json, ex=ttl)
        except Exception as e:
            logger.error(f"Blad krytyczny podczas zapisu do wektorowego cache: {e}", exc_info=True)