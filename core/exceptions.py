class DomainException(Exception):
    """Базовое исключение для бизнес-логики приложения."""
    pass

class DatabaseAlreadyExistsError(DomainException):
    """Вызывается, если база данных с таким именем уже зарегистрирована."""
    def __init__(self, db_name: str):
        # 1. Первым делом инициализируем базовый класс Exception текстовым сообщением
        self.message = f"База данных '{db_name}' уже существует."
        super().__init__(self.message)
        self.db_name = db_name


class OnboardingFailedError(DomainException):
    """Вызывается, если процесс создания или индексации воркспейса аварийно прервался."""
    def __init__(self, reason: str):
        self.reason = reason
        self.message = f"Ошибка онбординга базы данных: {reason}"
        super().__init__(self.message)


class WorkspaceNotFoundError(DomainException):
    """Вызывается, если запрашиваемый воркспейс не найден в реестре."""
    def __init__(self, workspace_id: str):
        super().__init__(f"Рабочее пространство с ID '{workspace_id}' не найдено.")
