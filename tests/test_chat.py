"""
Tests for the receptionist chat API.

Note: These tests mock the LLM to ensure predictable behavior.
In production, the actual LLM provides intent classification.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Intent, IntentClassification, SlotExtraction


client = TestClient(app)


# Mock LLM responses for predictable testing
def mock_intent_classification(intent: Intent, confidence: float = 0.95):
    """Create a mock intent classification result."""
    return IntentClassification(
        intent=intent,
        confidence=confidence,
        reasoning="Test mock",
    )


def mock_slot_extraction(**slots):
    """Create a mock slot extraction result."""
    return SlotExtraction(**slots)


class TestChatEndpoint:
    """Tests for the /chat endpoint."""

    def test_health_check(self):
        """Health endpoint returns ok."""
        response = client.get("/api/v1/receptionist/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @patch("app.core.graph.get_llm")
    def test_greeting_returns_chitchat_response(self, mock_llm):
        """Greeting messages are handled as chitchat."""
        # Mock the LLM to return chitchat intent
        mock_llm.return_value.with_structured_output.return_value.invoke.return_value = (
            mock_intent_classification(Intent.CHITCHAT)
        )
        
        response = client.post(
            "/api/v1/receptionist/chat",
            json={"session_id": "test-1", "message": "Hello!"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "needs_input"
        assert "help" in payload["response"].lower() or "scheduling" in payload["response"].lower()

    @patch("app.core.graph.get_llm")
    def test_booking_with_missing_slots_asks_for_info(self, mock_llm):
        """Booking request with missing info prompts for more details."""
        # First call: intent classification returns BOOK
        # Second call: slot extraction returns partial slots
        mock_structured = mock_llm.return_value.with_structured_output.return_value
        mock_structured.invoke.side_effect = [
            mock_intent_classification(Intent.BOOK),
            mock_slot_extraction(appointment_type="consultation"),  # Missing date/time
        ]
        
        response = client.post(
            "/api/v1/receptionist/chat",
            json={"session_id": "test-2", "message": "I want to book a consultation"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == "book"
        assert payload["status"] == "needs_input"
        # Should ask for missing date and time
        assert "date" in payload["response"].lower() or "time" in payload["response"].lower()

    @patch("app.core.graph.get_llm")
    def test_booking_with_complete_slots_asks_confirmation(self, mock_llm):
        """Complete booking request asks for confirmation."""
        mock_structured = mock_llm.return_value.with_structured_output.return_value
        mock_structured.invoke.side_effect = [
            mock_intent_classification(Intent.BOOK),
            mock_slot_extraction(
                appointment_type="consultation",
                preferred_date="tomorrow",
                preferred_time="2 PM",
            ),
        ]
        
        response = client.post(
            "/api/v1/receptionist/chat",
            json={
                "session_id": "test-3",
                "message": "Book a consultation tomorrow at 2 PM",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == "book"
        # Should ask for confirmation
        assert payload["awaiting_confirmation"] is True or "confirm" in payload["response"].lower()

    def test_escalation_request_transfers_to_human(self):
        """Request for human agent triggers escalation."""
        response = client.post(
            "/api/v1/receptionist/chat",
            json={"session_id": "test-4", "message": "I want to speak to a human"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["intent"] == "escalate"
        assert payload["status"] == "escalated"
        assert "human" in payload["response"].lower() or "transfer" in payload["response"].lower()


class TestSessionState:
    """Tests for session state management."""

    def test_get_nonexistent_session_returns_not_found(self):
        """Getting state for unknown session returns not_found."""
        response = client.get("/api/v1/receptionist/session/nonexistent-session")
        assert response.status_code == 200
        assert response.json()["status"] == "not_found"
