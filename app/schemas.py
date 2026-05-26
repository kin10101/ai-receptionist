from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    CONFIRM = "confirm"
    ESCALATE = "escalate"
    UNKNOWN = "unknown"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Latest user utterance.")
    session_id: str = Field(default="default-session")


class ChatResponse(BaseModel):
    session_id: str
    intent: Intent
    status: str
    response: str
    next_action: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
