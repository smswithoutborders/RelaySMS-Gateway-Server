"""Decode and publish RelaySMS payloads."""

import base64
import logging
import json

from src.grpc_publisher_client import publish_content
from src.bridge_server_grpc_client import publish_bridge_content

logger = logging.getLogger(__name__)


def decode_and_publish(request_data):
    """Decodes and publishes the RelaySMS payload based on the content."""

    if isinstance(request_data, str):
        try:
            request_data = json.loads(request_data)
        except json.JSONDecodeError:
            return None, "Invalid JSON data"

    text = request_data.get("text")
    sender = request_data.get("MSISDN") or request_data.get("address")

    if not text:
        return None, "Missing required field: text"
    if not sender:
        return None, "Missing required field: address or MSISDN"

    try:
        payload_bytes = base64.b64decode(text)
    except (ValueError, TypeError):
        return None, "Invalid Base64-encoded payload"

    is_bridge_payload = payload_bytes[0] == 0

    if is_bridge_payload:
        content = base64.b64encode(payload_bytes[1:]).decode("utf-8")
        publish_response, publish_error = publish_bridge_content(
            content=content, phone_number=sender
        )
    else:
        publish_response, publish_error = publish_content(content=text, sender=sender)

    if publish_error:
        logger.error("✖ gRPC error: %s", publish_error.code())
        return None, publish_error.details()

    if not publish_response.success:
        logger.error("✖ gRPC error: %s", publish_response.message)
        return None, publish_response.message

    logger.info("✔ Payload published successfully.")
    return (
        publish_response.message
        if is_bridge_payload
        else publish_response.publisher_response
    ), None
