from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Nazwa projektu wykorzystywana w logach i metadanych runtime
    PROJECT_NAME: str = "AEGIS-LLM-GATEWAY"

    # Klucz API do Gemini (LLM backend)
    GEMINI_API_KEY: str = ""

    # Tryb uruchomienia aplikacji (development / production)
    ENVIRONMENT: str = "development"

    # Redis – cache i szybka warstwa stanowa
    REDIS_URL: str = "redis://redis-cache:6379/0"

    # Qdrant – baza wektorowa (semantyczne wyszukiwanie cache)
    QDRANT_HOST: str = "qdrant-vector-db"
    QDRANT_PORT: int = 6333

    @property
    def QDRANT_URL(self) -> str:
        # Centralna konstrukcja URL dla klienta Qdrant
        return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"

    # Warstwa kompatybilności SRE:
    # mapowanie GEMINI -> OPENAI, żeby istniejące moduły nie wymagały refactoru
    @property
    def OPENAI_API_KEY(self) -> str:
        return self.GEMINI_API_KEY

    class Config:
        # Automatyczne ładowanie zmiennych środowiskowych z pliku .env
        env_file = ".env"

        # Ignorowanie dodatkowych zmiennych (bez crashy przy rozszerzeniach środowiska)
        extra = "ignore"


# Globalna instancja konfiguracji aplikacji (singleton runtime config)
settings = Settings()