from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./fogguard.db"
    CORS_ORIGINS: str = '["http://localhost:5173","http://localhost:3000"]'
    SIMULATION_MODE: bool = True
    SIMULATION_INTERVAL_MS: int = 1000
    DATA_RETENTION_DAYS: int = 30
    MAX_RANGE_CM: float = 400.0
    CRITICAL_THRESHOLD_CM: float = 50.0
    WARNING_THRESHOLD_CM: float = 100.0
    CAUTION_THRESHOLD_CM: float = 150.0

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except Exception:
            return ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
