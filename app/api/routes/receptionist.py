from fastapi import APIRouter

from app.core.graph import get_graph_state, run_receptionist_graph
from app.schemas import ChatRequest, ChatResponse, Intent

router = APIRouter(prefix="/receptionist", tags=["receptionist"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """
    Process a chat message through the receptionist graph.
    
    The graph handles:
    - Intent classification (LLM-based)
    - Slot extraction and validation
    - Action confirmation flow
    - Tool execution (calendar, email)
    - Human escalation
    """
    # Check if we're resuming from a confirmation interrupt
    current_state = get_graph_state(request.session_id)
    resume = (
        current_state is not None
        and current_state.get("awaiting_confirmation", False)
        and request.message.lower() in ("yes", "confirm", "no", "cancel")
    )
    
    state = run_receptionist_graph(
        request.message,
        request.session_id,
        resume_after_confirmation=resume,
    )
    
    return ChatResponse(
        session_id=request.session_id,
        intent=Intent(state.get("intent", Intent.UNKNOWN.value)),
        status=state.get("status", "needs_input"),
        response=state.get("response_text", ""),
        next_action=state.get("next_action"),
        data=state.get("data", {}),
        awaiting_confirmation=state.get("awaiting_confirmation", False),
    )


@router.get("/session/{session_id}")
def get_session_state(session_id: str) -> dict:
    """Get the current state of a session."""
    state = get_graph_state(session_id)
    if state is None:
        return {"session_id": session_id, "status": "not_found"}
    
    return {
        "session_id": session_id,
        "intent": state.get("intent"),
        "collected_slots": state.get("collected_slots", {}),
        "awaiting_confirmation": state.get("awaiting_confirmation", False),
        "status": state.get("status"),
    }
