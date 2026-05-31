import pytest
from config.common_config import settings

# python -m pytest -v

def test_config_load():
    """Тест проверяет, что критически важные настройки успешно загрузились."""
    assert settings.openrouter_api_key is not None
    assert settings.pg_host != ""
    assert settings.qdrant_url.startswith(("http://", "https://", "grpc://"))

def test_db_port_is_valid():
    """Тест проверяет корректность порта базы данных."""
    assert isinstance(settings.pg_port, int)
    assert 1 <= settings.pg_port <= 65535
