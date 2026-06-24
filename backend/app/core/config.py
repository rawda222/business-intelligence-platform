"""
Application Configuration & Settings
Loads configuration from environment variables and .env file
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Priority order:
    1. Environment variables (highest)
    2. .env file
    3. Default values (lowest)
    """
    
    # ========================================================
    # Application
    # ========================================================
    APP_NAME: str = "Business Intelligence Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = True
    
    # ========================================================
    # API Server
    # ========================================================
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # ========================================================
    # Security
    # ========================================================
    SECRET_KEY: str = "change-this-in-production-please"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # ========================================================
    # CORS (Cross-Origin Resource Sharing)
    # ========================================================
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    
    # ========================================================
    # Database URLs
    # ========================================================
    DATABASE_URL: str = "postgresql+asyncpg://bi_user:bi_password@localhost:5432/bi_platform"
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "bi_platform_reports"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # ========================================================
    # Vertex AI / Gemini
    # ========================================================
    GOOGLE_CLOUD_PROJECT: str = "applied-tractor-499314-e3"
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    VERTEX_AI_LOCATION: str = "us-central1"
    VERTEX_AI_MODEL: str = "gemini-2.5-flash"
    GOOGLE_GENAI_USE_VERTEXAI: bool = True
    
    # ========================================================
    # Pydantic Settings Configuration
    # ========================================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# ========================================================
# Create a single global instance
# ========================================================
settings = Settings()