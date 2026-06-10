from typing import List

from fastapi import APIRouter, File, Form, UploadFile, status, Path
from fastapi.responses import StreamingResponse
from schemas.chat import WorkspaceResponse
from services.onboard_service import create_workspace
from services.run_agent_service import run_agent_stream
from utils.pg_db import fetch_user_workspaces, fetch_workspace_by_id

router = APIRouter(prefix="/api/onboard", tags=["Onboard/Workspace API"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def onboard_workspace(
    name: str = Form(..., description="Имя воркспейса для UI"),
    description: str = Form(None, description="Описание воркспейса"),
    sql_file: UploadFile = File(..., description="DDL скрипт структуры таблиц"),
    few_shot_file: UploadFile = File(..., description="JSON файл с примерами запросов")
):
    result = await create_workspace(
        name=name,
        description=description,
        sql_file=sql_file,
        few_shot_file=few_shot_file
    )
    
    return result

@router.get(
    "/workspaces", 
    response_model=List[WorkspaceResponse], 
    status_code=status.HTTP_200_OK
)
async def get_workspaces_endpoint():
    """Возвращает список всех воркспейсов, созданных текущим пользователем."""
    # @todo Заменить на id из сессии/JWT-токена пользователя после реализации авторизации
    user_id = 1 
    
    # Прямо вызываем нашу асинхронную функцию из утилит
    workspaces = await fetch_user_workspaces(user_id=user_id)
    return workspaces

@router.get(
    "/workspace/{workspace_id}", 
    response_model=WorkspaceResponse, 
    status_code=status.HTTP_200_OK
)
async def get_workspace_by_id_endpoint(
    workspace_id: str = Path(..., description="UUID искомого рабочего пространства")
):
    """Возвращает информацию о конкретном воркспейсе по его уникальному ID."""
    workspace = await fetch_workspace_by_id(workspace_id=workspace_id)
    return workspace

