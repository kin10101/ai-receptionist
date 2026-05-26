from typing import Any, TypedDict


class ReceptionistState(TypedDict, total=False):
    session_id: str
    user_message: str
    intent: str
    collected_slots: dict[str, Any]
    missing_slots: list[str]
    status: str
    next_action: str
    response_text: str
    data: dict[str, Any]
    escalation_required: bool
    handoff_summary: str
