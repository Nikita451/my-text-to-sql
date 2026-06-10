from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from core.exceptions import DatabaseAlreadyExistsError, DomainException

async def db_already_exists_handler(request: Request, exc: Exception) -> JSONResponse:
    """Перехватчик ошибки дублирования БД."""
    assert isinstance(exc, DatabaseAlreadyExistsError)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message}
    )

async def global_domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Универсальный перехватчик для всех остальных бизнес-ошибок.
    Общий обработчик для ошибок DomainException и наследников
    """
    assert isinstance(exc, DomainException)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )

def setup_exception_handlers(app: FastAPI) -> None:
    """Функция-регистратор. Подключает все перехватчики к приложению."""
    # Порядок важен: от частных ошибок к более общим
    app.add_exception_handler(DatabaseAlreadyExistsError, db_already_exists_handler)
    app.add_exception_handler(DomainException, global_domain_exception_handler)
