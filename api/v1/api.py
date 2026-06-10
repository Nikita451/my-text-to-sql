from fastapi import APIRouter
from api.v1.endpoints import chat
from api.v1.endpoints import workspace
from api.v1.endpoints import test

api_router = APIRouter()

# Подключаем все роутеры v1
api_router.include_router(workspace.router)
api_router.include_router(chat.router)
api_router.include_router(test.router)
