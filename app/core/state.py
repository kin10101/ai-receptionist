from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class PendingAction(TypedDict, total=False):
    """Action awaiting user confirmation before execution."""
    action_type: str  # "book", "cancel", "reschedule"
    description: str  # Human-readable summary
    slots: dict[str, Any]  # Parameters for the action


class ReceptionistState(TypedDict, total=False):
    """
    Comprehensive state for the receptionist agent.
    
    Supports multi-turn conversations with:
    - Message history (checkpointed)
    - Intent classification with confidence
    - Slot filling with validation
    - Confirmation loops before executing actions
    - Escalation handling
    """
    # Session & Messages
    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    user_message: str  # Latest user input (convenience field)
    
    # Intent Classification
    intent: str
    intent_confidence: float
    
    # Slot Collection
    collected_slots: dict[str, Any]
    missing_slots: list[str]
    slot_validation_errors: list[str]
    
    # Action Confirmation
    pending_action: PendingAction | None
    awaiting_confirmation: bool
    user_confirmed: bool | None  # True=yes, False=no, None=not yet answered
    
    # Tool Execution
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    
    # Response
    status: str  # "in_progress", "needs_input", "completed", "escalated"
    next_action: str
    response_text: str
    data: dict[str, Any]
    
    # Escalation
    escalation_required: bool
    handoff_summary: str
