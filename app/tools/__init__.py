"""External tool adapters for the receptionist agent."""

from app.tools.gmail import (
    send_cancellation_email,
    send_confirmation_email,
    send_reminder_email,
)
from app.tools.google_calendar import (
    cancel_calendar_event,
    check_calendar_availability,
    create_calendar_event,
    get_upcoming_appointments,
    reschedule_calendar_event,
)

__all__ = [
    # Gmail tools
    "send_confirmation_email",
    "send_cancellation_email",
    "send_reminder_email",
    # Calendar tools
    "check_calendar_availability",
    "create_calendar_event",
    "cancel_calendar_event",
    "reschedule_calendar_event",
    "get_upcoming_appointments",
]
