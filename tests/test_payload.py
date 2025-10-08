"""Tests for payload_service.py."""

from unittest.mock import Mock, patch
import base64
import json
import pytest


from src.payload_service import decode_and_publish, BRIDGE_REQUEST_IDENTIFIER


class TestDecodeAndPublish:
    """Test decode_and_publish core functionality."""

    @pytest.fixture
    def valid_payload(self):
        """Create a valid test payload."""
        return {
            "text": base64.b64encode(b"\x01test_content").decode("utf-8"),
            "MSISDN": "+1234567890",
            "date": 1633024800000,
            "date_sent": 1633024800000,
        }

    @pytest.mark.parametrize(
        "payload_input, error_message",
        [
            ("invalid json", "Invalid JSON format"),
            (
                {"MSISDN": "+123", "date": 123, "date_sent": 123},
                "Missing required field: text",
            ),
            (
                {
                    "text": "not_valid_base64!!!",
                    "MSISDN": "+123",
                    "date": 123,
                    "date_sent": 123,
                },
                "Invalid Base64-encoded payload",
            ),
        ],
    )
    def test_invalid_inputs(self, payload_input, error_message):
        """Test decode_and_publish handles invalid inputs correctly."""
        result, error = decode_and_publish(payload_input, "http")
        assert result is None
        assert error == error_message

    @pytest.mark.parametrize("payload_type", ["dict", "json_string"])
    @patch("src.payload_service.publish_content")
    def test_successful_publish(self, mock_publish, valid_payload, payload_type):
        """Test successful payload publishing with dict and JSON string."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.publisher_response = "Published successfully"
        mock_publish.return_value = (mock_response, None)

        payload = (
            json.dumps(valid_payload)
            if payload_type == "json_string"
            else valid_payload
        )
        result, error = decode_and_publish(payload, "http")

        assert error is None
        assert result == "Published successfully"
        mock_publish.assert_called_once()

    @patch("src.payload_service.publish_content")
    def test_timestamp_conversion(self, mock_publish, valid_payload):
        """Test timestamps are converted from milliseconds to seconds."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.publisher_response = "Published"
        mock_publish.return_value = (mock_response, None)

        decode_and_publish(valid_payload, "http")

        call_kwargs = mock_publish.call_args[1]
        assert call_kwargs["date"] == "1633024800"
        assert call_kwargs["date_sent"] == "1633024800"

    @patch("src.payload_service.publish_content")
    def test_grpc_error_handling(self, mock_publish, valid_payload):
        """Test gRPC error is properly returned."""
        mock_error = Mock()
        mock_error.code.return_value = "UNAVAILABLE"
        mock_error.details.return_value = "Service unavailable"
        mock_publish.return_value = (None, mock_error)

        result, error = decode_and_publish(valid_payload, "http")

        assert result is None
        assert error == "Service unavailable"

    @patch("src.payload_service.publish_content")
    def test_unsuccessful_response(self, mock_publish, valid_payload):
        """Test unsuccessful publish response is handled."""
        mock_response = Mock()
        mock_response.success = False
        mock_response.message = "Publishing failed"
        mock_publish.return_value = (mock_response, None)

        result, error = decode_and_publish(valid_payload, "http")

        assert result is None
        assert error == "Publishing failed"


class TestBridgePayloads:
    """Test bridge payload specific functionality."""

    @pytest.fixture
    def bridge_payload(self):
        """Create a bridge payload."""
        return {
            "text": base64.b64encode(
                bytes([BRIDGE_REQUEST_IDENTIFIER]) + b"bridge_content"
            ).decode("utf-8"),
            "MSISDN": "+1234567890",
            "date": 1633024800000,
            "date_sent": 1633024800000,
        }

    @patch("src.payload_service.DISABLE_BRIDGE_PAYLOADS_OVER_HTTP", True)
    def test_bridge_http_disabled(self, bridge_payload):
        """Test bridge payloads are rejected over HTTP when disabled."""
        result, error = decode_and_publish(bridge_payload, "http")

        assert result is None
        assert error == "Bridge payloads over HTTP are restricted."

    @pytest.mark.parametrize("origin", ["smtp", "ftp"])
    @patch("src.payload_service.publish_bridge_content")
    def test_bridge_non_http_allowed(self, mock_publish, bridge_payload, origin):
        """Test bridge payloads are allowed over non-HTTP transports."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.message = "Bridge published"
        mock_publish.return_value = (mock_response, None)

        result, error = decode_and_publish(bridge_payload, origin)

        assert error is None
        assert result == "Bridge published"
        mock_publish.assert_called_once()

    @patch("src.payload_service.DISABLE_BRIDGE_PAYLOADS_OVER_HTTP", False)
    @patch("src.payload_service.publish_bridge_content")
    def test_bridge_content_extraction(self, mock_publish, bridge_payload):
        """Test bridge content is correctly extracted (without identifier byte)."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.message = "Published"
        mock_publish.return_value = (mock_response, None)

        decode_and_publish(bridge_payload, "http")

        call_kwargs = mock_publish.call_args[1]
        sent_content = call_kwargs["content"]
        decoded = base64.b64decode(sent_content)
        assert decoded == b"bridge_content"
