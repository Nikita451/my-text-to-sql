from datetime import datetime
from pydantic import BaseModel, Field


# Описываем структуру входящего запроса от фронтэнда
class ChatRequest(BaseModel):
    message: str = Field(..., description="Текстовый вопрос пользователя к базе данных")
    db_name: str = Field(..., description="Идентификатор БД")
    col_name: str = Field(..., description="Идентификатор коллекции")
    thread_id: str = Field("default_web_thread", description="Идентификатор сессии для работы памяти диалога")

class WorkspaceResponse(BaseModel):
    id: str = Field(..., description="Уникальный UUID воркспейса")
    name: str = Field(..., description="Отображаемое имя воркспейса")
    internal_db_name: str = Field(..., description="Системное имя базы данных")
    internal_col_name: str = Field(..., description="Системное имя коллекции")
    description: str | None = Field(None, description="Описание воркспейса")
    created_at: datetime = Field(..., description="Дата создания")

