"""
Production-ready receptionist agent graph.

Architecture:
- LLM-based intent classification with confidence scoring
- Multi-turn conversation support via checkpointing
- Slot-filling loop with validation
- Confirmation flow before executing actions
- Tool integration for calendar and email operations
- Graceful escalation to human agents
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.core.state import PendingAction, ReceptionistState
from app.handoff.escalation import build_handoff_summary, should_escalate
from app.schemas import (
    Intent,
    IntentClassification,
    REQUIRED_SLOTS,
    SlotExtraction,
)
from app.tools.gmail import send_confirmation_email, send_cancellation_email
from app.tools.google_calendar import (
    cancel_calendar_event,
    check_calendar_availability,
    create_calendar_event,
    get_upcoming_appointments,
    reschedule_calendar_event,
)

# ============================================================================
# LLM Setup
# ============================================================================

def get_llm(temperature: float = 0.0) -> ChatOpenAI:
    """Get configured LLM instance."""
    return ChatOpenAI(
        model=settings.llm_model,
        temperature=temperature,
        api_key=settings.openai_api_key or None,
    )


# ============================================================================
# Tools Configuration
# ============================================================================

RECEPTIONIST_TOOLS = [
    check_calendar_availability,
    create_calendar_event,
    cancel_calendar_event,
    reschedule_calendar_event,
    get_upcoming_appointments,
    send_confirmation_email,
    send_cancellation_email,
]

tool_node = ToolNode(RECEPTIONIST_TOOLS)


# ============================================================================
# Prompts
# ============================================================================

INTENT_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an AI receptionist assistant. Classify the user's intent from their message.

Available intents:
- book: User wants to schedule/book a new appointment
- reschedule: User wants to change an existing appointment to a different time
- cancel: User wants to cancel an existing appointment
- confirm: User wants to confirm an existing appointment
- check_availability: User is asking about available times without committing to book
- chitchat: General conversation, greetings, or off-topic messages
- escalate: User explicitly asks for a human agent or manager
- unknown: Cannot determine intent

Consider the conversation history for context. Be confident in your classification."""),
    ("human", "Conversation so far:\n{history}\n\nLatest message: {message}"),
])

SLOT_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """Extract appointment-related information from the user's message.

Extract these slots if mentioned:
- appointment_type: Type of appointment (consultation, follow-up, checkup, general)
- preferred_date: When they want the appointment (e.g., "tomorrow", "next Monday", "January 15th")
- preferred_time: What time they prefer (e.g., "2 PM", "morning", "afternoon")
- patient_name: Name of the patient if mentioned
- contact_info: Phone number or email if mentioned
- reason: Reason for the appointment if mentioned

Only extract information explicitly stated. Do not infer or assume values."""),
    ("human", "Message: {message}"),
])

RESPONSE_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a friendly and professional AI receptionist for a medical office.

Your personality:
- Warm and welcoming
- Clear and concise
- Professional but not robotic
- Helpful and proactive

Current context:
- Intent: {intent}
- Collected information: {slots}
- Missing information: {missing}
- Status: {status}

Generate a natural response based on the context. If information is missing, ask for it conversationally.
Keep responses brief (1-2 sentences) unless more detail is needed."""),
    ("human", "{message}"),
])


# ============================================================================
# Node Functions
# ============================================================================

def load_context_node(state: ReceptionistState) -> ReceptionistState:
    """
    Load conversation context and prepare state.
    First node in the graph - sets up the conversation.
    """
    user_message = state.get("user_message", "")
    
    # Add the new user message to history
    new_messages = [HumanMessage(content=user_message)]
    
    return {
        "messages": new_messages,
        "awaiting_confirmation": False,
        "user_confirmed": None,
    }


def classify_intent_node(state: ReceptionistState) -> ReceptionistState:
    """
    Use LLM to classify user intent with confidence scoring.
    """
    user_message = state.get("user_message", "")
    messages = state.get("messages", [])  # Used for building history
    
    # Check for explicit escalation keywords first (fast path)
    if should_escalate(user_message):
        return {
            "intent": Intent.ESCALATE.value,
            "intent_confidence": 1.0,
            "escalation_required": True,
        }
    
    # Check if user is responding to a confirmation prompt
    awaiting = state.get("awaiting_confirmation", False)
    if awaiting:
        lowered = user_message.lower()
        if any(word in lowered for word in ("yes", "confirm", "correct", "that's right", "book it", "sounds good")):
            return {
                "intent": "confirm_action",
                "intent_confidence": 1.0,
                "user_confirmed": True,
            }
        if any(word in lowered for word in ("no", "cancel", "wrong", "change", "different")):
            return {
                "intent": "reject_action",
                "intent_confidence": 1.0,
                "user_confirmed": False,
            }
    
    # Build conversation history string
    history_str = ""
    for msg in messages[:-1]:  # Exclude current message
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        history_str += f"{role}: {msg.content}\n"
    
    # Use LLM for classification with structured output
    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)
    
    chain = INTENT_CLASSIFICATION_PROMPT | structured_llm
    
    try:
        result: IntentClassification = chain.invoke({
            "history": history_str or "No prior conversation",
            "message": user_message,
        })
        
        return {
            "intent": result.intent.value,
            "intent_confidence": result.confidence,
            "escalation_required": result.intent == Intent.ESCALATE,
        }
    except (ValueError, KeyError, AttributeError):
        # Fallback to unknown if LLM fails or returns invalid data
        return {
            "intent": Intent.UNKNOWN.value,
            "intent_confidence": 0.0,
            "escalation_required": False,
        }


def extract_slots_node(state: ReceptionistState) -> ReceptionistState:
    """
    Use LLM to extract slots from user message.
    Merges with previously collected slots.
    """
    user_message = state.get("user_message", "")
    existing_slots = state.get("collected_slots", {})
    intent = state.get("intent", Intent.UNKNOWN.value)
    
    llm = get_llm()
    structured_llm = llm.with_structured_output(SlotExtraction)
    
    chain = SLOT_EXTRACTION_PROMPT | structured_llm
    
    try:
        extracted: SlotExtraction = chain.invoke({"message": user_message})
        
        # Merge extracted slots with existing (new values override)
        new_slots = {**existing_slots}
        for field, value in extracted.model_dump().items():
            if value is not None:
                new_slots[field] = value
        
        # Determine missing required slots for this intent
        try:
            intent_enum = Intent(intent)
            required = REQUIRED_SLOTS.get(intent_enum, [])
            missing = [
                slot.value for slot in required
                if slot.value not in new_slots or not new_slots[slot.value]
            ]
        except ValueError:
            missing = []
        
        return {
            "collected_slots": new_slots,
            "missing_slots": missing,
        }
    except (ValueError, KeyError, AttributeError):
        return {
            "collected_slots": existing_slots,
            "missing_slots": [],
        }


def validate_slots_node(state: ReceptionistState) -> ReceptionistState:
    """
    Validate collected slots for correctness.
    """
    slots = state.get("collected_slots", {})
    errors = []
    
    # Example validations
    if "preferred_time" in slots:
        time_str = slots["preferred_time"].lower()
        # Basic time format validation
        if not any(indicator in time_str for indicator in ("am", "pm", "morning", "afternoon", "evening", ":")):
            errors.append("preferred_time format unclear")
    
    return {"slot_validation_errors": errors}


def prepare_confirmation_node(state: ReceptionistState) -> ReceptionistState:
    """
    Prepare action summary for user confirmation.
    """
    intent = state.get("intent", "")
    slots = state.get("collected_slots", {})
    session_id = state.get("session_id", "default")
    
    # Build confirmation message based on intent
    if intent == Intent.BOOK.value:
        apt_type = slots.get("appointment_type", "appointment")
        date = slots.get("preferred_date", "the requested date")
        time = slots.get("preferred_time", "the requested time")
        
        pending = PendingAction(
            action_type="book",
            description=f"Book a {apt_type} for {date} at {time}",
            slots=slots,
        )
        
        response = (
            f"I'll book a {apt_type} for {date} at {time}. "
            "Does that sound correct?"
        )
        
    elif intent == Intent.CANCEL.value:
        pending = PendingAction(
            action_type="cancel",
            description="Cancel your upcoming appointment",
            slots={"session_id": session_id},
        )
        response = "I'll cancel your upcoming appointment. Is that okay?"
        
    elif intent == Intent.RESCHEDULE.value:
        date = slots.get("preferred_date", "the new date")
        time = slots.get("preferred_time", "the new time")
        
        pending = PendingAction(
            action_type="reschedule",
            description=f"Reschedule to {date} at {time}",
            slots=slots,
        )
        response = f"I'll reschedule your appointment to {date} at {time}. Confirm?"
    else:
        pending = None
        response = ""
    
    return {
        "pending_action": pending,
        "awaiting_confirmation": True,
        "status": "needs_confirmation",
        "next_action": "await_confirmation",
        "response_text": response,
        "data": {"pending_action": pending},
    }


def execute_action_node(state: ReceptionistState) -> ReceptionistState:
    """
    Execute the confirmed action using tools.
    """
    pending = state.get("pending_action")
    session_id = state.get("session_id", "default")
    slots = state.get("collected_slots", {})
    
    if not pending:
        return {
            "status": "error",
            "response_text": "No action to execute.",
        }
    
    action_type = pending.get("action_type", "")
    
    if action_type == "book":
        result = create_calendar_event.invoke({
            "session_id": session_id,
            "appointment_type": slots.get("appointment_type", "general"),
            "date": slots.get("preferred_date", "TBD"),
            "time": slots.get("preferred_time", "TBD"),
            "patient_name": slots.get("patient_name", "Patient"),
            "notes": slots.get("reason", ""),
        })
        
        if result.get("status") == "created":
            apt = result.get("appointment", {})
            return {
                "status": "completed",
                "next_action": "done",
                "response_text": (
                    f"Your {apt.get('appointment_type')} is confirmed for "
                    f"{apt.get('date')} at {apt.get('time')}. "
                    "You'll receive a confirmation shortly."
                ),
                "data": {"appointment": apt},
                "pending_action": None,
                "awaiting_confirmation": False,
                "messages": [AIMessage(content=f"Booked appointment: {apt}")],
            }
    
    elif action_type == "cancel":
        result = cancel_calendar_event.invoke({
            "session_id": session_id,
        })
        
        if result.get("status") == "cancelled":
            return {
                "status": "completed",
                "next_action": "done",
                "response_text": "Your appointment has been cancelled. Is there anything else I can help with?",
                "data": {"cancelled": True},
                "pending_action": None,
                "awaiting_confirmation": False,
            }
        else:
            return {
                "status": "error",
                "response_text": "I couldn't find an appointment to cancel. Could you provide more details?",
                "pending_action": None,
                "awaiting_confirmation": False,
            }
    
    elif action_type == "reschedule":
        result = reschedule_calendar_event.invoke({
            "session_id": session_id,
            "new_date": slots.get("preferred_date", ""),
            "new_time": slots.get("preferred_time", ""),
        })
        
        if result.get("status") == "rescheduled":
            apt = result.get("appointment", {})
            return {
                "status": "completed",
                "next_action": "done",
                "response_text": f"Your appointment has been rescheduled to {apt.get('date')} at {apt.get('time')}.",
                "data": {"appointment": apt},
                "pending_action": None,
                "awaiting_confirmation": False,
            }
    
    return {
        "status": "error",
        "response_text": "Something went wrong. Let me transfer you to a human agent.",
        "escalation_required": True,
    }


def ask_for_slots_node(state: ReceptionistState) -> ReceptionistState:
    """
    Generate a natural prompt for missing information.
    """
    missing = state.get("missing_slots", [])
    slots = state.get("collected_slots", {})
    
    # Map slot names to friendly prompts
    slot_prompts = {
        "appointment_type": "what type of appointment you need",
        "preferred_date": "which date works for you",
        "preferred_time": "what time you prefer",
        "patient_name": "the patient's name",
        "contact_info": "a contact number or email",
    }
    
    if len(missing) == 1:
        prompt = f"Could you tell me {slot_prompts.get(missing[0], missing[0])}?"
    elif len(missing) == 2:
        prompts = [slot_prompts.get(m, m) for m in missing]
        prompt = f"I just need {prompts[0]} and {prompts[1]}."
    else:
        prompts = [slot_prompts.get(m, m) for m in missing[:3]]
        prompt = f"To proceed, I'll need: {', '.join(prompts)}."
    
    return {
        "status": "needs_input",
        "next_action": "provide_slots",
        "response_text": prompt,
        "data": {"missing_slots": missing, "collected_slots": slots},
    }


def check_availability_node(state: ReceptionistState) -> ReceptionistState:
    """
    Check calendar availability and present options.
    """
    slots = state.get("collected_slots", {})
    date = slots.get("preferred_date", "tomorrow")
    apt_type = slots.get("appointment_type", "general")
    
    result = check_calendar_availability.invoke({
        "date": date,
        "appointment_type": apt_type,
    })
    
    available = result.get("available_slots", [])
    
    if available:
        slots_str = ", ".join(available[:5])  # Show max 5
        response = f"Here are the available slots for {date}: {slots_str}. Which time works best for you?"
    else:
        response = f"I don't see any availability for {date}. Would you like to try a different date?"
    
    return {
        "status": "needs_input",
        "next_action": "select_slot",
        "response_text": response,
        "data": {"available_slots": available, "date": date},
    }


def chitchat_node(state: ReceptionistState) -> ReceptionistState:
    """
    Handle general conversation / greetings.
    """
    user_message = state.get("user_message", "").lower()
    
    greetings = ("hi", "hello", "hey", "good morning", "good afternoon")
    thanks = ("thank", "thanks", "appreciate")
    
    if any(g in user_message for g in greetings):
        response = "Hello! I'm your scheduling assistant. I can help you book, reschedule, or cancel appointments. How can I help you today?"
    elif any(t in user_message for t in thanks):
        response = "You're welcome! Is there anything else I can help you with?"
    else:
        response = "I'm here to help with scheduling appointments. Would you like to book, reschedule, or cancel an appointment?"
    
    return {
        "status": "needs_input",
        "next_action": "await_intent",
        "response_text": response,
        "data": {},
        "messages": [AIMessage(content=response)],
    }


def escalate_node(state: ReceptionistState) -> ReceptionistState:
    """
    Handle escalation to human agent.
    """
    summary = build_handoff_summary(state)
    
    return {
        "status": "escalated",
        "next_action": "handoff_to_human",
        "handoff_summary": summary,
        "response_text": (
            "I understand you'd like to speak with someone. "
            "I'm transferring you to a human agent who can better assist you. "
            "Please hold for a moment."
        ),
        "data": {"handoff_summary": summary},
    }


def handle_rejection_node(state: ReceptionistState) -> ReceptionistState:
    """
    Handle when user rejects a proposed action.
    """
    pending = state.get("pending_action")
    action_type = pending.get("action_type", "") if pending else ""
    
    if action_type == "book":
        response = "No problem. What would you like to change - the date, time, or type of appointment?"
    elif action_type == "reschedule":
        response = "Okay, let's try again. What date and time would work better for you?"
    else:
        response = "Alright, I've cancelled that. What would you like to do instead?"
    
    return {
        "status": "needs_input",
        "next_action": "revise_action",
        "response_text": response,
        "pending_action": None,
        "awaiting_confirmation": False,
        "user_confirmed": None,
        # Keep collected slots so user can modify rather than start over
    }


# ============================================================================
# Routing Functions
# ============================================================================

def route_after_intent(state: ReceptionistState) -> str:
    """Route based on classified intent."""
    intent = state.get("intent", "")
    
    if state.get("escalation_required"):
        return "escalate"
    
    if intent == "confirm_action":
        return "execute"
    
    if intent == "reject_action":
        return "handle_rejection"
    
    if intent == Intent.CHITCHAT.value:
        return "chitchat"
    
    if intent in (Intent.BOOK.value, Intent.RESCHEDULE.value, Intent.CANCEL.value):
        return "extract_slots"
    
    if intent == Intent.CHECK_AVAILABILITY.value:
        return "check_availability"
    
    if intent == Intent.CONFIRM.value:
        return "execute"
    
    # Unknown or unclear intent
    return "chitchat"


def route_after_slots(state: ReceptionistState) -> str:
    """Route based on slot completeness."""
    missing = state.get("missing_slots", [])
    errors = state.get("slot_validation_errors", [])
    
    if errors:
        return "ask_for_slots"
    
    if missing:
        return "ask_for_slots"
    
    return "confirm"


# ============================================================================
# Graph Construction
# ============================================================================

def build_receptionist_graph() -> StateGraph:
    """
    Build the production receptionist graph with all nodes and edges.
    """
    graph = StateGraph(ReceptionistState)
    
    # Add all nodes
    graph.add_node("load_context", load_context_node)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("extract_slots", extract_slots_node)
    graph.add_node("validate_slots", validate_slots_node)
    graph.add_node("ask_for_slots", ask_for_slots_node)
    graph.add_node("confirm", prepare_confirmation_node)
    graph.add_node("execute", execute_action_node)
    graph.add_node("check_availability", check_availability_node)
    graph.add_node("chitchat", chitchat_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("handle_rejection", handle_rejection_node)
    
    # Define edges
    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "classify_intent")
    
    # Route after intent classification
    graph.add_conditional_edges(
        "classify_intent",
        route_after_intent,
        {
            "escalate": "escalate",
            "chitchat": "chitchat",
            "extract_slots": "extract_slots",
            "check_availability": "check_availability",
            "execute": "execute",
            "handle_rejection": "handle_rejection",
        },
    )
    
    # Slot extraction -> validation -> routing
    graph.add_edge("extract_slots", "validate_slots")
    graph.add_conditional_edges(
        "validate_slots",
        route_after_slots,
        {
            "ask_for_slots": "ask_for_slots",
            "confirm": "confirm",
        },
    )
    
    # Terminal nodes
    graph.add_edge("ask_for_slots", END)
    graph.add_edge("confirm", END)
    graph.add_edge("execute", END)
    graph.add_edge("check_availability", END)
    graph.add_edge("chitchat", END)
    graph.add_edge("escalate", END)
    graph.add_edge("handle_rejection", END)
    
    return graph


# ============================================================================
# Compiled Graph with Checkpointing
# ============================================================================

# Memory checkpointer for session persistence
checkpointer = MemorySaver()

# Build and compile the graph
_graph_builder = build_receptionist_graph()
_compiled_graph = _graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["execute"],  # Pause before executing actions for confirmation
)


def run_receptionist_graph(
    message: str,
    session_id: str,
    resume_after_confirmation: bool = False,
) -> ReceptionistState:
    """
    Run the receptionist graph with checkpointing support.
    
    Args:
        message: User's message
        session_id: Session identifier for conversation continuity
        resume_after_confirmation: If True, resume from interrupt point
    
    Returns:
        Final state after graph execution
    """
    config = {"configurable": {"thread_id": session_id}}
    
    if resume_after_confirmation:
        # Resume from interrupt point
        return _compiled_graph.invoke(None, config=config)
    
    # Start new invocation
    payload: ReceptionistState = {
        "session_id": session_id,
        "user_message": message,
    }
    
    return _compiled_graph.invoke(payload, config=config)


def get_graph_state(session_id: str) -> ReceptionistState | None:
    """Get the current state for a session."""
    config = {"configurable": {"thread_id": session_id}}
    snapshot = _compiled_graph.get_state(config)
    return snapshot.values if snapshot else None
