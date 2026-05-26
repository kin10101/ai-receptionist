from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_chat_requires_missing_slots_when_booking_is_incomplete():
    response = client.post(
        "/api/v1/receptionist/chat",
        json={"session_id": "s1", "message": "I want to book an appointment"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "book"
    assert payload["status"] == "needs_input"
    assert "appointment_type" in payload["data"]["missing_slots"]
    assert "preferred_time" in payload["data"]["missing_slots"]


def test_chat_suggests_slots_for_tomorrow_afternoon_consultation():
    response = client.post(
        "/api/v1/receptionist/chat",
        json={"session_id": "s2", "message": "Book a consultation tomorrow afternoon"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "book"
    assert payload["next_action"] == "select_slot"
    assert "available_slots" in payload["data"]
    assert payload["data"]["available_slots"] == ["tomorrow 2 PM", "tomorrow 4 PM"]
