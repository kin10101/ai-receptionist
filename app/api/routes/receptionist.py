from fastapi import APIRouter

from app.core.graph import run_receptionist_graph
from app.schemas import ChatRequest, ChatResponse, Intent

router = APIRouter(prefix="/receptionist", tags=["receptionist"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    state = run_receptionist_graph(request.message, request.session_id)
    return ChatResponse(
        session_id=request.session_id,
        intent=Intent(state.get("intent", Intent.UNKNOWN.value)),
        status=state.get("status", "needs_input"),
        response=state.get("response_text", ""),
        next_action=state.get("next_action"),
        data=state.get("data", {}),
    )
