"""Decode and publish RelaySMS payloads."""

import base64
import logging
import json
from typing import Tuple, Optional, Union, Dict, Any

from src.grpc_publisher_client import publish_content
from src.bridge_server_grpc_client import publish_bridge_content
from src.utils import get_configs

logger = logging.getLogger(__name__)

BRIDGE_REQUEST_IDENTIFIER = 0
TIMESTAMP_DIVISOR = 1000

DISABLE_BRIDGE_PAYLOADS_OVER_HTTP = (
    get_configs("DISABLE_BRIDGE_PAYLOADS_OVER_HTTP", default_value="false").lower()
    == "true"
)


def _obfuscate_sender_id(sender_id: str) -> str:
    """Obfuscate sender ID for privacy in logs.

    Args:
        sender_id: The sender identifier to obfuscate.

    Returns:
        Obfuscated sender ID showing first 3 and last 2 characters.
        Example: +1234567890 -> +12*****90
    """
    if not sender_id or len(sender_id) <= 5:
        return "***"
    return f"{sender_id[:3]}{'*' * (len(sender_id) - 5)}{sender_id[-2:]}"


def _validate_payload_fields(payload: Dict[str, Any]) -> Optional[str]:
    """Validate required fields in the payload.

    Args:
        payload: The payload dictionary to validate.

    Returns:
        Error message if validation fails, None otherwise.
    """
    encoded_content = payload.get("text")
    sender_id = payload.get("MSISDN") or payload.get("address")
    date = payload.get("date")
    date_sent = payload.get("date_sent")

    if not encoded_content:
        return "Missing required field: text"
    if not sender_id:
        return "Missing required field: address or MSISDN"
    if not date:
        return "Missing required field: date"
    if not date_sent:
        return "Missing required field: date_sent"

    return None


def _convert_timestamp(timestamp: Optional[Union[int, str]]) -> Optional[str]:
    """Convert timestamp from milliseconds to seconds.

    Args:
        timestamp: The timestamp to convert (in milliseconds).

    Returns:
        The converted timestamp as a string or the original value if None.
    """
    if timestamp is None:
        return None
    try:
        return str(int(timestamp) // TIMESTAMP_DIVISOR)
    except (ValueError, TypeError):
        return str(timestamp)


def decode_and_publish(
    payload: Union[str, Dict[str, Any]], request_origin: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Decodes and publishes the RelaySMS payload based on the request origin.

    Args:
        payload: The incoming request payload containing the data. Can be a JSON string
            or a dictionary with keys: 'text' (base64-encoded content), 'MSISDN' or
            'address' (sender identifier), 'date', and 'date_sent'.
        request_origin: The origin of the request, either 'http', 'smtp' or 'ftp'.
            Used to enforce security policies.

    Returns:
        A tuple of (message, error). On success, returns (response_message, None).
        On failure, returns (None, error_message).

    Raises:
        None. All errors are returned as part of the tuple.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.error("✖ Failed to parse JSON payload: %s", str(e))
            return None, "Invalid JSON format"

    validation_error = _validate_payload_fields(payload)
    if validation_error:
        logger.error("✖ Payload validation failed: %s", validation_error)
        return None, validation_error

    encoded_content = payload["text"]
    sender_id = payload.get("MSISDN") or payload["address"]
    date = payload["date"]
    date_sent = payload["date_sent"]

    try:
        decoded_bytes = base64.b64decode(encoded_content)
    except (ValueError, TypeError) as e:
        logger.error("✖ Base64 decoding failed: %s", str(e))
        return None, "Invalid Base64-encoded payload"

    if not decoded_bytes:
        logger.error("✖ Decoded payload is empty")
        return None, "Decoded payload is empty"

    is_bridge_request = decoded_bytes[0] == BRIDGE_REQUEST_IDENTIFIER

    if (
        is_bridge_request
        and request_origin == "http"
        and DISABLE_BRIDGE_PAYLOADS_OVER_HTTP
    ):
        logger.warning(
            "✖ Bridge payload rejected: HTTP transport disabled for sender %s",
            _obfuscate_sender_id(sender_id),
        )
        return None, "Bridge payloads over HTTP are restricted."

    if is_bridge_request:
        bridge_content = base64.b64encode(decoded_bytes[1:]).decode("utf-8")
        logger.debug("Publishing bridge content for sender: %s", sender_id)
        publish_response, publish_error = publish_bridge_content(
            content=bridge_content, phone_number=sender_id
        )
    else:
        logger.debug("Publishing regular content for sender: %s", sender_id)
        publish_response, publish_error = publish_content(
            content=encoded_content,
            sender=sender_id,
            date=_convert_timestamp(date),
            date_sent=_convert_timestamp(date_sent),
        )

    if publish_error:
        logger.error(
            "✖ gRPC publishing failed - Code: %s, Details: %s",
            publish_error.code(),
            publish_error.details(),
        )
        return None, publish_error.details()

    if not publish_response.success:
        logger.error("✖ Publishing failed - Response: %s", publish_response.message)
        return None, publish_response.message

    logger.info(
        "✔ Payload published successfully - Origin: %s, Sender: %s, Type: %s",
        request_origin,
        _obfuscate_sender_id(sender_id),
        "bridge" if is_bridge_request else "regular",
    )
    return (
        publish_response.message
        if is_bridge_request
        else publish_response.publisher_response
    ), None
