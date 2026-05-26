from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    BOOK = "book"
    RESCHEDULE = "reschedule"
    CANCEL = "cancel"
    CONFIRM = "confirm"
    CHECK_AVAILABILITY = "check_availability"
    CHITCHAT = "chitchat"
    ESCALATE = "escalate"
    UNKNOWN = "unknown"


class AppointmentType(str, Enum):
    CONSULTATION = "consultation"
    FOLLOW_UP = "follow_up"
    CHECKUP = "checkup"
    GENERAL = "general"


class SlotName(str, Enum):
    APPOINTMENT_TYPE = "appointment_type"
    PREFERRED_DATE = "preferred_date"
    PREFERRED_TIME = "preferred_time"
    PATIENT_NAME = "patient_name"
    CONTACT_INFO = "contact_info"
    REASON = "reason"


# Slot requirements per intent
REQUIRED_SLOTS: dict[Intent, list[SlotName]] = {
    Intent.BOOK: [SlotName.APPOINTMENT_TYPE, SlotName.PREFERRED_DATE, SlotName.PREFERRED_TIME],
    Intent.RESCHEDULE: [SlotName.PREFERRED_DATE, SlotName.PREFERRED_TIME],
    Intent.CANCEL: [],  # We'll look up by session
    Intent.CONFIRM: [],
    Intent.CHECK_AVAILABILITY: [SlotName.PREFERRED_DATE],
}


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
    awaiting_confirmation: bool = False


class IntentClassification(BaseModel):
    """Structured output for LLM intent classification."""
    intent: Intent = Field(description="The detected user intent")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: str = Field(description="Brief explanation for the classification")


class SlotExtraction(BaseModel):
    """Structured output for LLM slot extraction."""
    appointment_type: str | None = Field(default=None, description="Type of appointment")
    preferred_date: str | None = Field(default=None, description="Preferred date (e.g., 'tomorrow', 'Monday')")
    preferred_time: str | None = Field(default=None, description="Preferred time (e.g., '2 PM', 'afternoon')")
    patient_name: str | None = Field(default=None, description="Patient's name if mentioned")
    contact_info: str | None = Field(default=None, description="Phone or email if mentioned")
    reason: str | None = Field(default=None, description="Reason for appointment if mentioned")
