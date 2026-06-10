from fastapi import APIRouter
from services.onboard_service import create_workspace
from services.run_agent_service import run_agent_stream

router = APIRouter(prefix="", tags=["Onboard/Workspace API"])


@router.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI works 555!"}

