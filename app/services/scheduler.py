from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class InMemoryScheduler:
    appointments: dict[str, dict[str, Any]] = field(default_factory=dict)

    def check_availability(self, appointment_type: str, window: str) -> list[str]:
        if appointment_type.lower() == "consultation" and "tomorrow afternoon" in window.lower():
            return ["tomorrow 2 PM", "tomorrow 4 PM"]
        return ["next available: 10 AM"]

    def create_appointment(self, session_id: str, appointment_type: str, preferred_time: str) -> dict[str, Any]:
        appointment_id = f"apt-{uuid4().hex[:8]}"
        event = {
            "appointment_id": appointment_id,
            "session_id": session_id,
            "appointment_type": appointment_type,
            "time": preferred_time,
        }
        self.appointments[appointment_id] = event
        return event

    def cancel_latest_for_session(self, session_id: str) -> bool:
        for appointment_id, event in list(self.appointments.items()):
            if event["session_id"] == session_id:
                del self.appointments[appointment_id]
                return True
        return False

    def confirm_latest_for_session(self, session_id: str) -> dict[str, Any] | None:
        for event in self.appointments.values():
            if event["session_id"] == session_id:
                return event
        return None
