from app.core.state import ReceptionistState


def should_escalate(message: str) -> bool:
    lowered = message.lower()
    escalation_terms = ("human", "representative", "agent", "manager", "escalate")
    return any(term in lowered for term in escalation_terms)


def build_handoff_summary(state: ReceptionistState) -> str:
    return (
        "Escalation requested. "
        f"Intent={state.get('intent', 'unknown')}; "
        f"Message={state.get('user_message', '')}; "
        f"Collected={state.get('collected_slots', {})}."
    )
