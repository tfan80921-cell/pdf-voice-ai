"""
Central configuration using pydantic-settings.
All secrets and tunable parameters live here.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "PDF Voice AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    CHROMA_PERSIST_DIR: Path = BASE_DIR / "chroma_db"
    STATIC_DIR: Path = BASE_DIR / "static"

    # ChromaDB
    CHROMA_COLLECTION_NAME: str = "pdf_documents"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_RESULTS: int = 5

    # AI defaults (overridden by request)
    DEFAULT_PROVIDER: str = "gemini"
    DEFAULT_MODEL_GEMINI: str = "gemini-1.5-flash"
    DEFAULT_MODEL_DEEPSEEK: str = "deepseek-chat"
    DEFAULT_MODEL_GLM: str = "glm-4-flash"

    # Rate limiting / safety
    MAX_UPLOAD_SIZE_MB: int = 50
    MAX_PDF_PAGES: int = 500
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".txt", ".md", ".csv", ".json", ".log"}

    def ensure_dirs(self) -> None:
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
