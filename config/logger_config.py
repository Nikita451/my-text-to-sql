import logging
import colorlog

def setup_logging():
    """Централизованная настройка цветного логирования."""
    
    # Настраиваем цвета для каждого уровня
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',       # INFO будет зеленым
        'WARNING': 'yellow',   # WARNING желтым
        'ERROR': 'red',        # ERROR красным
        'CRITICAL': 'red,bg_white',
    }

    # Создаем форматтер от colorlog. 
    # %(log_color)s включает цвет, %(reset)s возвращает стандартный цвет терминала
    formatter = colorlog.ColoredFormatter(
        fmt="%(asctime)s [%(log_color)s%(levelname)s%(reset)s] %(message)s",
        datefmt="%H:%M:%S",
        log_colors=log_colors
    )

    # Настраиваем вывод в консоль (StreamHandler)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Применяем настройки к корневому (!) логгеру
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Очищаем старые хендлеры, чтобы логи не дублировались
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)

    # Приглушаем логи от тяжелых сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


