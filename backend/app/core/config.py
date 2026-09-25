from pathlib import Path
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FinReview API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Server & CORS
    BACKEND_PORT: int = 8000
    CORS_ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://finreview.vercel.app",
    ]
    CORS_ORIGINS: Optional[str] = None
    
    # JWT Authentication Configuration
    JWT_SECRET_KEY: str = "finreview-default-jwt-secret-key-32-chars-min"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    AUTH_COOKIE_NAME: str = "finreview_refresh_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        if not v or not v.strip() or len(v.strip()) < 32:
            raise ValueError("JWT_SECRET_KEY must be explicitly configured and at least 32 characters long.")
        return v.strip()

    @field_validator("DATABASE_URL")
    @classmethod
    def canonicalize_database_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v and v.startswith("sqlite:///") and not v.startswith("sqlite:///:memory:"):
            path_part = v.replace("sqlite:///", "")
            if not Path(path_part).is_absolute():
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                clean_path = path_part.lstrip("./\\")
                canonical = (project_root / clean_path).as_posix()
                return f"sqlite:///{canonical}"
        return v

    def get_cors_origins(self) -> List[str]:
        origins = list(self.CORS_ALLOWED_ORIGINS)
        if self.CORS_ORIGINS:
            for item in self.CORS_ORIGINS.split(","):
                cleaned = item.strip()
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins
    
    # Database (Default to PostgreSQL)
    DATABASE_URL: str = "postgresql://app_user:finpassword@localhost:5432/finreview"
    
    # LLM Configuration (DeepSeek & Ollama)
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-flash"
    DEEPSEEK_TIMEOUT_SECONDS: float = 30.0
    DEEPSEEK_MAX_RETRIES: int = 2

    # Ollama Assistant Configuration
    OLLAMA_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "https://ollama.com/v1"
    OLLAMA_MODEL: str = "nemotron-3-nano:30b"
    OLLAMA_FAST_MODEL: str = "nemotron-3-nano:30b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0

    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "nemotron-3-nano:30b"

    # Redis & Celery Background Workers
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    @property
    def deepseek_api_key(self) -> Optional[str]:
        return self.DEEPSEEK_API_KEY

    @property
    def deepseek_base_url(self) -> str:
        return self.DEEPSEEK_BASE_URL

    @property
    def deepseek_model(self) -> str:
        return self.DEEPSEEK_MODEL

    @property
    def ollama_api_key(self) -> Optional[str]:
        return self.OLLAMA_API_KEY

    @property
    def ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def ollama_model(self) -> str:
        return self.OLLAMA_MODEL

    # Financial Materiality Config
    VARIANCE_PERCENTAGE_THRESHOLD: float = 10.0  # 10%
    VARIANCE_DOLLAR_THRESHOLD: float = 1000.0   # $1,000

    _project_root = Path(__file__).resolve().parent.parent.parent.parent
    _root_env = _project_root / ".env"

    model_config = SettingsConfigDict(
        env_file=(str(_root_env), ".env", "../.env"),
        extra="ignore",
    )


settings = Settings()
