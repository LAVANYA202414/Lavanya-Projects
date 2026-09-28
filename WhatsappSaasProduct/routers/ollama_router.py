from fastapi import APIRouter , Depends
from uuid import UUID

from services.ollama_service import AIResponseService

service = AIResponseService()


# configure router
router = APIRouter(
    prefix="/ollama",
    tags= ["Ollama"]
)

@router.post("/ai-response")
def get_ai_response(
    user_message : str
):

    return service.user_query_response(user_message)
