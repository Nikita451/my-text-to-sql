import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Приватная переменная-заглушка
_executor: ThreadPoolExecutor | None = None

def init_fastembed_executors() -> None:
    """Инициализирует пул потоков при старте приложения."""
    global _executor
    logger.info("Инициализация кастомного пула потоков для FastEmbed...")
    # 1. Создаем кастомный пул потоков операционной системы при старте приложения
    # max_workers=4 означает, что внутри ОС будет создано ровно 4 "рабочих" потока.
    # Сколько бы запросов ни пришло, FastEmbed не займет больше 4 потоков процессора.
    # Преимущество над asyncio.to_thread - мы контролируем число потоков. 
    _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="FastEmbed")

def close_fastembed_executors() -> None:
    """Безопасно закрывает пул потоков, ожидая завершения запущенных задач."""
    global _executor
    if _executor:
        logger.info("Завершение работы пула потоков FastEmbed...")
        # wait=True гарантирует, что мы не убьем поток посреди генерации эмбеддинга
        _executor.shutdown(wait=True)
        _executor = None

def get_fastembed_executor() -> ThreadPoolExecutor:
    """Геттер для получения пула потоков внутри бизнес-логики."""
    if _executor is None:
        raise RuntimeError("Пул потоков не инициализирован! Вызовите init_executors() в lifespan.")
    return _executor
