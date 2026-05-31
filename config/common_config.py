from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # default=...  - Обязательное значение без нач значения. 
    openrouter_api_key: str = Field(default=...)

    qdrant_url: str = Field(default=...)
    pg_db: str = Field(default=...)
    pg_user: str = Field(default=...)
    pg_password: str = Field(default=...)
    pg_host: str = Field(default=...)
    pg_port: int = Field(default=...)
    
    # Настройки для Pydantic: указываем файл окружения
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()

if __name__ == "__main__":
    # локальный запуск из config-директории
    from logger_config import setup_logging
    setup_logging()
    logger.info("Конфигурация успешно загружена.")
    logger.info(f"Qdrant подключен к: {settings.qdrant_url}")


