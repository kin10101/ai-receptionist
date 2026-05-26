import re
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.state import ReceptionistState
from app.handoff.escalation import build_handoff_summary, should_escalate
from app.schemas import Intent
from app.services.scheduler import InMemoryScheduler

scheduler = InMemoryScheduler()


def _detect_intent(message: str) -> Intent:
    lowered = message.lower()
    if any(word in lowered for word in ("book", "schedule", "appointment")):
        return Intent.BOOK
    if any(word in lowered for word in ("reschedule", "move")):
        return Intent.RESCHEDULE
    if any(word in lowered for word in ("cancel", "delete")):
        return Intent.CANCEL
    if "confirm" in lowered:
        return Intent.CONFIRM
    if should_escalate(lowered):
        return Intent.ESCALATE
    return Intent.UNKNOWN


def detect_intent_node(state: ReceptionistState) -> ReceptionistState:
    intent = _detect_intent(state.get("user_message", ""))
    return {"intent": intent.value, "escalation_required": intent == Intent.ESCALATE}


def collect_slots_node(state: ReceptionistState) -> ReceptionistState:
    message = state.get("user_message", "").lower()
    intent = state.get("intent", Intent.UNKNOWN.value)
    slots: dict[str, Any] = {}
    missing: list[str] = []

    if "consultation" in message:
        slots["appointment_type"] = "consultation"
    elif "follow up" in message or "follow-up" in message:
        slots["appointment_type"] = "follow-up"

    if "tomorrow afternoon" in message:
        slots["preferred_time"] = "tomorrow afternoon"
    elif re.search(r"\b2\s?pm\b", message):
        slots["preferred_time"] = "tomorrow 2 PM"
    elif re.search(r"\b4\s?pm\b", message):
        slots["preferred_time"] = "tomorrow 4 PM"

    if intent == Intent.BOOK.value:
        for key in ("appointment_type", "preferred_time"):
            if key not in slots:
                missing.append(key)

    return {"collected_slots": slots, "missing_slots": missing}


def _route_after_collection(state: ReceptionistState) -> str:
    if state.get("escalation_required"):
        return "escalate"
    if state.get("missing_slots"):
        return "missing"
    return "execute"


def ask_for_missing_details_node(state: ReceptionistState) -> ReceptionistState:
    missing_slots = state.get("missing_slots", [])
    missing_text = ", ".join(missing_slots)
    return {
        "status": "needs_input",
        "next_action": "provide_missing_details",
        "response_text": f"Got it. I still need: {missing_text}.",
        "data": {"missing_slots": missing_slots},
    }


def execute_scheduling_node(state: ReceptionistState) -> ReceptionistState:
    intent = state.get("intent", Intent.UNKNOWN.value)
    slots = state.get("collected_slots", {})
    session_id = state.get("session_id", "default-session")

    if intent == Intent.BOOK.value:
        appointment_type = slots.get("appointment_type", "consultation")
        preferred_time = slots.get("preferred_time", "tomorrow afternoon")
        if preferred_time == "tomorrow afternoon":
            available = scheduler.check_availability(appointment_type, preferred_time)
            return {
                "status": "needs_input",
                "next_action": "select_slot",
                "response_text": (
                    f"I found available {appointment_type} slots at {available[0]} and {available[1]}. "
                    "Which one works for you?"
                ),
                "data": {"available_slots": available},
            }

        event = scheduler.create_appointment(session_id, appointment_type, preferred_time)
        return {
            "status": "completed",
            "next_action": "done",
            "response_text": (
                f"Great. Your {appointment_type} is scheduled for {event['time']}."
            ),
            "data": {"appointment": event},
        }

    if intent == Intent.CANCEL.value:
        cancelled = scheduler.cancel_latest_for_session(session_id)
        return {
            "status": "completed" if cancelled else "needs_input",
            "next_action": "done" if cancelled else "provide_appointment_details",
            "response_text": "Your latest appointment has been cancelled." if cancelled else "I could not find an appointment to cancel yet.",
            "data": {"cancelled": cancelled},
        }

    if intent == Intent.CONFIRM.value:
        event = scheduler.confirm_latest_for_session(session_id)
        return {
            "status": "completed" if event else "needs_input",
            "next_action": "done" if event else "provide_appointment_details",
            "response_text": (
                f"Your appointment is confirmed for {event['time']}."
                if event
                else "I could not find an appointment to confirm yet."
            ),
            "data": {"appointment": event},
        }

    if intent == Intent.RESCHEDULE.value:
        return {
            "status": "needs_input",
            "next_action": "provide_reschedule_details",
            "response_text": "Sure. Please share your current appointment time and preferred new time.",
            "data": {},
        }

    return {
        "status": "needs_input",
        "next_action": "clarify_intent",
        "response_text": "I can help with booking, rescheduling, cancelling, or confirming appointments. What would you like to do?",
        "data": {},
    }


def escalate_node(state: ReceptionistState) -> ReceptionistState:
    return {
        "status": "escalated",
        "next_action": "handoff_to_human",
        "handoff_summary": build_handoff_summary(state),
        "response_text": "Understood. I’m transferring you to a human agent now.",
        "data": {"handoff_summary": build_handoff_summary(state)},
    }


def build_receptionist_graph():
    graph_builder = StateGraph(ReceptionistState)
    graph_builder.add_node("detect_intent", detect_intent_node)
    graph_builder.add_node("collect_slots", collect_slots_node)
    graph_builder.add_node("ask_for_missing", ask_for_missing_details_node)
    graph_builder.add_node("execute", execute_scheduling_node)
    graph_builder.add_node("escalate", escalate_node)

    graph_builder.add_edge(START, "detect_intent")
    graph_builder.add_edge("detect_intent", "collect_slots")
    graph_builder.add_conditional_edges(
        "collect_slots",
        _route_after_collection,
        {
            "missing": "ask_for_missing",
            "execute": "execute",
            "escalate": "escalate",
        },
    )
    graph_builder.add_edge("ask_for_missing", END)
    graph_builder.add_edge("execute", END)
    graph_builder.add_edge("escalate", END)
    return graph_builder.compile()


_graph = build_receptionist_graph()


def run_receptionist_graph(message: str, session_id: str) -> ReceptionistState:
    payload: ReceptionistState = {
        "session_id": session_id,
        "user_message": message,
    }
    return _graph.invoke(payload)
