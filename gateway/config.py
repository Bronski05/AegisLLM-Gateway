from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AEGIS-LLM-GATEWAY"
    GEMINI_API_KEY: str = ""
    ENVIRONMENT: str = "development"
    
    REDIS_URL: str = "redis://redis-cache:6379/0"
    QDRANT_HOST: str = "qdrant-vector-db"
    QDRANT_PORT: int = 6333

    @property
    def QDRANT_URL(self) -> str:
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # SRE Bridge: zapobiega crashom cache.py/routing.py bez brudzenia pliku .env
    @property
    def OPENAI_API_KEY(self) -> str:
        return self.GEMINI_API_KEY

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()