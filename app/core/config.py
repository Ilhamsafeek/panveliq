"""
Configuration settings for PanvelIQ
Loads environment variables from .env file
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields from .env
    )
    
    # Application Settings
    APP_NAME: str = "PanvelIQ"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_VERSION: str = "v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database Configuration
    DATABASE_URL: str
    DB_ECHO: bool = False
    
    # Security & Authentication
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS Settings (will be split from comma-separated string)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4"
    
    # DALL-E
    DALLE_API_KEY: Optional[str] = None
    
    # Mailchimp
    MAILCHIMP_API_KEY: Optional[str] = None
    MAILCHIMP_SERVER_PREFIX: Optional[str] = None
    MAILCHIMP_LIST_ID: Optional[str] = None
    
    # WhatsApp
    WHATSAPP_API_KEY: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    
    # Meta (Facebook & Instagram)
    META_APP_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_ACCESS_TOKEN: Optional[str] = None
    
    # LinkedIn
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None
    
    # Google Ads
    GOOGLE_ADS_CUSTOMER_ID: Optional[str] = None
    GOOGLE_ADS_DEVELOPER_TOKEN: Optional[str] = None
    GOOGLE_ADS_CLIENT_ID: Optional[str] = None
    GOOGLE_ADS_CLIENT_SECRET: Optional[str] = None
    GOOGLE_ADS_REFRESH_TOKEN: Optional[str] = None
    
    # Google PageSpeed
    PAGESPEED_API_KEY: Optional[str] = None
    
    # Google Search Console
    SEARCH_CONSOLE_SITE_URL: Optional[str] = None
    SEARCH_CONSOLE_SERVICE_ACCOUNT_EMAIL: Optional[str] = None
    
    # Google Analytics 4
    GOOGLE_ANALYTICS_4_PROPERTY_ID: Optional[str] = None
    
    # Moz
    MOZ_ACCESS_ID: Optional[str] = None
    MOZ_SECRET_KEY: Optional[str] = None
    
    # Canva
    CANVA_API_KEY: Optional[str] = None
    CANVA_TEAM_ID: Optional[str] = None
    
    # Synthesia
    SYNTHESIA_API_KEY: Optional[str] = None
    SYNTHESIA_AVATAR_ID: Optional[str] = None
    
    # File Storage
    UPLOAD_DIR: str = "./static/uploads"
    MAX_UPLOAD_SIZE: int = 10485760
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    
    # Frontend
    FRONTEND_URL: str = "http://localhost:8000"
    STATIC_URL: str = "/static"
    
    # Admin Credentials
    ADMIN_EMAIL: str = "admin@panveliq.com"
    ADMIN_PASSWORD: str = "password"
    
    @property
    def cors_origins(self) -> list[str]:
        """Convert comma-separated ALLOWED_ORIGINS string to list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


# Create settings instance
settings = Settings()