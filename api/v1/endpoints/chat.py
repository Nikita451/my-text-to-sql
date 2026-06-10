from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from schemas.chat import ChatRequest
from services.run_agent_service import run_agent_stream

router = APIRouter(prefix="/api/chat", tags=["Chat & AI Agent"])

@router.post("", status_code=status.HTTP_200_OK)
async def chat_endpoint(request: ChatRequest):
    """Эндпоинт для отправки сообщений агенту со стримингом процесса размышлений."""
    return StreamingResponse(
        run_agent_stream(request.message, request.thread_id, col_name=request.col_name, db_name=request.db_name),
        media_type="text/event-stream"
    )

