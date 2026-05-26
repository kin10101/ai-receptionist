from typing import Annotated

from langchain_core.tools import tool


@tool
def send_confirmation_email(
    recipient_email: Annotated[str, "Email address to send confirmation to"],
    appointment_type: Annotated[str, "Type of appointment"],
    appointment_time: Annotated[str, "Scheduled time for the appointment"],
    patient_name: Annotated[str, "Name of the patient"] = "Patient",
) -> dict:
    """
    Send a confirmation email for a scheduled appointment.
    Use this after successfully booking or rescheduling an appointment.
    """
    # In production, this would integrate with Gmail API
    return {
        "status": "sent",
        "message": f"Confirmation email sent to {recipient_email}",
        "details": {
            "recipient": recipient_email,
            "appointment_type": appointment_type,
            "appointment_time": appointment_time,
            "patient_name": patient_name,
        },
    }


@tool
def send_cancellation_email(
    recipient_email: Annotated[str, "Email address to send cancellation notice to"],
    appointment_id: Annotated[str, "ID of the cancelled appointment"],
    appointment_time: Annotated[str, "Original time of the cancelled appointment"],
) -> dict:
    """
    Send a cancellation confirmation email.
    Use this after successfully cancelling an appointment.
    """
    return {
        "status": "sent",
        "message": f"Cancellation confirmation sent to {recipient_email}",
        "details": {
            "recipient": recipient_email,
            "appointment_id": appointment_id,
            "original_time": appointment_time,
        },
    }


@tool
def send_reminder_email(
    recipient_email: Annotated[str, "Email address to send reminder to"],
    appointment_type: Annotated[str, "Type of appointment"],
    appointment_time: Annotated[str, "Scheduled time for the appointment"],
    hours_before: Annotated[int, "Hours before appointment to send reminder"] = 24,
) -> dict:
    """
    Schedule a reminder email to be sent before an appointment.
    """
    return {
        "status": "scheduled",
        "message": f"Reminder email scheduled for {hours_before} hours before appointment",
        "details": {
            "recipient": recipient_email,
            "appointment_type": appointment_type,
            "appointment_time": appointment_time,
            "reminder_hours": hours_before,
        },
    }


# Legacy class for backward compatibility
class GmailTool:
    """Placeholder adapter for Gmail confirmation actions."""

    def send_confirmation(self, *_args, **_kwargs):
        return {"status": "stubbed", "message": "Gmail confirmation scaffolded."}
