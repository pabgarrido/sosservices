"""SOS Services - Configuration"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://sosservices:changeme@db:5432/sosservices"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # API Keys
    openweathermap_api_key: Optional[str] = None
    nasa_firms_api_key: Optional[str] = None

    # IPMA (no key needed)
    ipma_base_url: str = "https://api.ipma.pt/open-data"

    # TomTom (optional, free tier)
    tomtom_api_key: Optional[str] = None

    # Ticketmaster Discovery API (free tier, developer.ticketmaster.com)
    ticketmaster_api_key: Optional[str] = None

    # Proteção Civil
    prociv_base_url: str = "https://www.prociv.pt"

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"
    log_level: str = "INFO"

    # CORS
    cors_allow_origins: str = "http://localhost:3000"
    cors_allow_credentials: bool = True

    # Portugal bounding box
    pt_lat_min: float = 36.96
    pt_lat_max: float = 42.15
    pt_lon_min: float = -9.50
    pt_lon_max: float = -6.19

    # Polling intervals (seconds)
    weather_poll_interval: int = 900       # 15 min
    fire_poll_interval: int = 600          # 10 min
    prociv_poll_interval: int = 300        # 5 min
    traffic_poll_interval: int = 300       # 5 min
    events_poll_interval: int = 3600       # 1 hour

    # Analytics
    correlation_interval: int = 60         # Run correlation every 60s
    hazard_radius_km: float = 10.0         # Radius for proximity-based correlation

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
