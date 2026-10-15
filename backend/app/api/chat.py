from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.answers.chat import ChatService, sse

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Anonymous conversation id made up by the client (e.g. a UUID); no authentication.
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.post("/chat")
async def chat(
    body: ChatRequest, service: Annotated[ChatService, Depends(get_chat_service)]
) -> StreamingResponse:
    """Server-sent events: `filters`, `listings`, `token`..., `done` (and `error` if search
    is unavailable). Listing cards come from database rows; the text never carries prices."""

    async def stream():
        async for event in service.events(body.message, body.session_id):
            yield sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
