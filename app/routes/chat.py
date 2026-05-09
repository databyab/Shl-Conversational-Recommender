from __future__ import annotations

from fastapi import APIRouter

from app.models.request_models import ChatRequest
from app.models.response_models import ChatResponse
from app.orchestrator.controller import handle_chat

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await handle_chat(request)
