from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # default=...  - Обязательное значение без нач значения. 
    openrouter_api_key: str = Field(default=...)
    langfuse_public_key: str = Field(default=...)
    langfuse_secret_key: str = Field(default=...)

    pg_password: str = Field(default=...)
    lf_pg_password: str = Field(default=...)

    pg_db: str = Field(default=...)
    lf_pg_db: str = Field(default=...)
    system_db_name: str = Field(default=...)


    # некритичные данные с дефолтным значением.
    # Инфраструктура
    pg_host: str = Field(default="localhost")
    pg_port: int = Field(default=5432)
    pg_user: str = Field(default="myuser")
    lf_pg_user: str = Field(default="langfuse")

    qdrant_url: str = Field(default="http://localhost:6333")
    langfuse_base_url: str = Field(default="http://localhost:3000")
    
    
    model: str = Field(default="deepseek/deepseek-chat")
    origin: str = Field(default="*")

    # Настройки для Pydantic: указываем файл окружения
    model_config = SettingsConfigDict(env_file=".env", 
                                      env_file_encoding="utf-8", 
                                      extra="ignore"  # ← Игнорировать лишние переменные
                                    )

settings = Settings()

if __name__ == "__main__":
    # локальный запуск из config-директории
    from logger_config import setup_logging
    setup_logging()
    logger.info("Конфигурация успешно загружена.")
    logger.info(f"Qdrant подключен к: {settings.qdrant_url}")


