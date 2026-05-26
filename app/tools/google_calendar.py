from typing import Annotated
from uuid import uuid4

from langchain_core.tools import tool


# In-memory store for demo purposes
_appointments: dict[str, dict] = {}


@tool
def check_calendar_availability(
    date: Annotated[str, "Date to check availability for (e.g., 'tomorrow', '2024-01-15')"],
    appointment_type: Annotated[str, "Type of appointment to check slots for"] = "general",
) -> dict:
    """
    Check available appointment slots for a given date.
    Returns a list of available time slots.
    """
    # In production, this would query Google Calendar API
    # For now, return mock availability
    available_slots = []
    
    if "tomorrow" in date.lower():
        available_slots = ["9:00 AM", "10:30 AM", "2:00 PM", "3:30 PM", "4:00 PM"]
    elif "monday" in date.lower():
        available_slots = ["9:00 AM", "11:00 AM", "2:00 PM"]
    else:
        available_slots = ["10:00 AM", "2:00 PM", "4:00 PM"]
    
    return {
        "status": "success",
        "date": date,
        "appointment_type": appointment_type,
        "available_slots": available_slots,
        "message": f"Found {len(available_slots)} available slots for {date}",
    }


@tool
def create_calendar_event(
    session_id: Annotated[str, "Session ID for tracking the appointment"],
    appointment_type: Annotated[str, "Type of appointment"],
    date: Annotated[str, "Date of the appointment"],
    time: Annotated[str, "Time of the appointment"],
    patient_name: Annotated[str, "Name of the patient"] = "Patient",
    notes: Annotated[str, "Additional notes for the appointment"] = "",
) -> dict:
    """
    Create a new calendar event for an appointment.
    Use this to book a new appointment after the user confirms.
    """
    appointment_id = f"apt-{uuid4().hex[:8]}"
    
    event = {
        "appointment_id": appointment_id,
        "session_id": session_id,
        "appointment_type": appointment_type,
        "date": date,
        "time": time,
        "patient_name": patient_name,
        "notes": notes,
        "status": "confirmed",
    }
    
    _appointments[appointment_id] = event
    
    return {
        "status": "created",
        "message": f"Appointment successfully created for {date} at {time}",
        "appointment": event,
    }


@tool
def cancel_calendar_event(
    appointment_id: Annotated[str, "ID of the appointment to cancel"] = "",
    session_id: Annotated[str, "Session ID to find latest appointment"] = "",
) -> dict:
    """
    Cancel an existing calendar event.
    Can cancel by appointment_id or by session_id (cancels the latest for that session).
    """
    target_id = appointment_id
    
    # If no appointment_id, find by session_id
    if not target_id and session_id:
        for apt_id, apt in _appointments.items():
            if apt.get("session_id") == session_id:
                target_id = apt_id
                break
    
    if target_id and target_id in _appointments:
        cancelled = _appointments.pop(target_id)
        return {
            "status": "cancelled",
            "message": "Appointment successfully cancelled",
            "cancelled_appointment": cancelled,
        }
    
    return {
        "status": "not_found",
        "message": "No appointment found to cancel",
    }


@tool
def reschedule_calendar_event(
    appointment_id: Annotated[str, "ID of the appointment to reschedule"] = "",
    session_id: Annotated[str, "Session ID to find latest appointment"] = "",
    new_date: Annotated[str, "New date for the appointment"] = "",
    new_time: Annotated[str, "New time for the appointment"] = "",
) -> dict:
    """
    Reschedule an existing appointment to a new date/time.
    """
    target_id = appointment_id
    
    if not target_id and session_id:
        for apt_id, apt in _appointments.items():
            if apt.get("session_id") == session_id:
                target_id = apt_id
                break
    
    if target_id and target_id in _appointments:
        old_event = _appointments[target_id]
        old_date = old_event.get("date")
        old_time = old_event.get("time")
        
        _appointments[target_id]["date"] = new_date or old_date
        _appointments[target_id]["time"] = new_time or old_time
        
        return {
            "status": "rescheduled",
            "message": f"Appointment rescheduled from {old_date} {old_time} to {new_date} {new_time}",
            "appointment": _appointments[target_id],
        }
    
    return {
        "status": "not_found",
        "message": "No appointment found to reschedule",
    }


@tool
def get_upcoming_appointments(
    session_id: Annotated[str, "Session ID to get appointments for"],
) -> dict:
    """
    Get all upcoming appointments for a session.
    """
    appointments = [
        apt for apt in _appointments.values()
        if apt.get("session_id") == session_id
    ]
    
    return {
        "status": "success",
        "appointments": appointments,
        "count": len(appointments),
    }


# Legacy class for backward compatibility
class GoogleCalendarTool:
    """Placeholder adapter for Google Calendar actions."""

    def check_slots(self, *_args, **_kwargs):
        return {"status": "stubbed", "message": "Google Calendar integration scaffolded."}

    def create_event(self, *_args, **_kwargs):
        return {"status": "stubbed", "message": "Event creation scaffolded."}
