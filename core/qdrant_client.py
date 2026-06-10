import logging
from typing import AsyncGenerator
from qdrant_client import AsyncQdrantClient
from config.common_config import settings  # Предполагаем, что у вас есть конфиг настроек

logger = logging.getLogger(__name__)

# Приватная переменная-синглтон
_qdrant_client: AsyncQdrantClient | None = None

def init_qdrant_client() -> None:
    """Инициализирует асинхронный клиент Qdrant при старте приложения."""
    global _qdrant_client
    logger.info("Инициализация асинхронного клиента Qdrant...")
    
    # Создаем клиент один раз. Он сам управляет пулом соединений внутри себя.
    _qdrant_client = AsyncQdrantClient(
        url=settings.qdrant_url
    )

async def close_qdrant_client() -> None:
    """Безопасно закрывает сетевые соединения с Qdrant при остановке."""
    global _qdrant_client
    if _qdrant_client:
        logger.info("Закрытие соединений с Qdrant...")
        # ОБЯЗАТЕЛЬНО для AsyncQdrantClient: закрываем сокеты/gRPC каналы
        await _qdrant_client.close()
        _qdrant_client = None

def get_qdrant_client() -> AsyncQdrantClient:
    """Геттер для использования напрямую в коде бизнес-логики (сервисах/утилитах)."""
    if _qdrant_client is None:
        raise RuntimeError("Qdrant клиент не инициализирован! Вызовите init_qdrant() в lifespan.")
    return _qdrant_client

async def get_qdrant_dependency() -> AsyncGenerator[AsyncQdrantClient, None]:
    """Альтернативный геттер-зависимость для использования в эндпойнтах FastAPI через Depends."""
    if _qdrant_client is None:
        raise RuntimeError("Qdrant клиент не инициализирован!")
    yield _qdrant_client
