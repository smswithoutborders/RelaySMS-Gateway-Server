"""Decode and publish RelaySMS payloads."""

import base64
import json
from typing import Tuple, Optional, Union, Dict, Any

from logutils import get_logger
from src.grpc_publisher_client import publish_content
from src.bridge_server_grpc_client import publish_bridge_content
from src.utils import get_configs
from src.payload_parser import PayloadParser
from src.segment_cache import SegmentCache

logger = get_logger(__name__)

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


def detect_payload_type(content: str) -> str:
    """Detect the type of the payload.

    Args:
        content: The payload string.

    Returns:
        Payload type identifier: 'image-text', 'bridge', 'platform'.
    """
    if PayloadParser.is_it_payload(content):
        return "image-text"

    if PayloadParser.is_bridge_payload(content):
        return "bridge"

    return "platform"


def _assemble_complete_payload(session_id: str, sender_id: str) -> Optional[str]:
    """Assemble all segments of a session into complete payload.

    Args:
        session_id: The session identifier.
        sender_id: The sender's phone number or identifier.

    Returns:
        The assembled base64 content or None if assembly fails.
    """
    segments = SegmentCache.get_segments(session_id, sender_id)

    if not segments:
        logger.error("No segments found for session %s", session_id)
        return None

    try:
        segments_sorted = sorted(segments, key=lambda s: s.segment_number)
        assembled_content = b"".join(seg.content for seg in segments_sorted)
        image_length = segments_sorted[0].image_length

        logger.debug(
            "Assembled %d segments for session %s, total length: %d bytes",
            len(segments_sorted),
            session_id,
            len(assembled_content),
        )

        return assembled_content.decode("utf-8"), image_length

    except Exception as e:
        logger.error(
            "Failed to assemble segments for session %s: %s", session_id, str(e)
        )
        return None


def _handle_image_text_payload(
    encoded_content: str,
    sender_id: str,
    date: str,
    date_sent: str,
    request_origin: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Handle image-text payload with segmentation and caching.

    Args:
        encoded_content: The image-text formatted payload string.
        sender_id: The sender's phone number or identifier.
        date: Message date timestamp.
        date_sent: Message sent timestamp.
        request_origin: The origin of the request ('http', 'smtp', 'ftp').

    Returns:
        Tuple of (message, error). Returns success message if segment stored
        or published, error message if processing fails.
    """
    parse_result = PayloadParser.parse_image_text_payload(encoded_content)
    if not parse_result:
        return None, "Failed to parse image-text payload"

    metadata, content = parse_result
    session_id = metadata["session_id"]

    success = SegmentCache.store_segment(
        session_id=session_id,
        sender_id=sender_id,
        segment_number=metadata["segment_number"],
        total_segments=metadata["total_segments"],
        image_length=metadata["image_length"],
        text_length=metadata["text_length"],
        content=content.encode("utf-8"),
    )

    if not success:
        return None, "Failed to store message segment"

    is_complete, received, total = SegmentCache.is_session_complete(
        session_id, sender_id
    )

    if not is_complete:
        logger.debug(
            "Session %s partial: %d/%d segments received. Waiting for more...",
            session_id,
            received,
            total,
        )
        return (
            f"Segment {received}/{total} received and cached for session {session_id}",
            None,
        )

    logger.info(
        "Session %s complete (%d/%d segments). Assembling and publishing...",
        session_id,
        received,
        total,
    )

    assembled_content, image_length = _assemble_complete_payload(session_id, sender_id)

    if not assembled_content:
        SegmentCache.delete_session(session_id, sender_id)
        return None, "Failed to assemble complete payload"

    # Recursively call decode_and_publish with assembled content
    # This allows the existing logic to handle bridge vs platform payloads
    assembled_payload = {
        "text": assembled_content,
        "address": sender_id,
        "date": date,
        "date_sent": date_sent,
        "image_length": image_length,
    }
    publish_message, publish_error = decode_and_publish(
        payload=assembled_payload, request_origin=request_origin
    )

    SegmentCache.delete_session(session_id, sender_id)

    if publish_error:
        logger.error(
            "✖ Publishing failed for session %s: %s",
            session_id,
            publish_error,
        )
        return None, publish_error

    logger.info(
        "✔ Image-text payload published successfully - Session: %s, Sender: %s",
        session_id,
        _obfuscate_sender_id(sender_id),
    )
    return publish_message, None


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

    payload_type = detect_payload_type(encoded_content)

    logger.debug("Detected payload type: %s from sender: %s", payload_type, sender_id)
    logger.debug("Payload content: %s", encoded_content)

    if payload_type == "image-text":
        logger.debug("Detected image-text payload from sender: %s", sender_id)
        return _handle_image_text_payload(
            encoded_content, sender_id, date, date_sent, request_origin
        )

    try:
        decoded_bytes = base64.b64decode(encoded_content)
    except (ValueError, TypeError) as e:
        logger.error("✖ Base64 decoding failed: %s", str(e))
        return None, "Invalid Base64-encoded payload"

    if not decoded_bytes:
        logger.error("✖ Decoded payload is empty")
        return None, "Decoded payload is empty"

    is_bridge_request = payload_type == "bridge"

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
        logger.debug(
            "Publishing Bridge Payload:\ncontent: %s\nsender: %s\nimage length: %s",
            bridge_content,
            sender_id,
            payload.get("image_length") or 0,
        )
        publish_response, publish_error = publish_bridge_content(
            content=bridge_content,
            phone_number=sender_id,
            image_length=payload.get("image_length"),
        )
    else:
        logger.debug(
            "Publishing Platform Payload:\ncontent: %s\nsender: %s",
            decoded_bytes,
            sender_id,
        )
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
        "bridge" if is_bridge_request else "platform",
    )
    return (
        publish_response.message
        if is_bridge_request
        else publish_response.publisher_response
    ), None
