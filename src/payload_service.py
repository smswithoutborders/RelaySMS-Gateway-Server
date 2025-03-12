"""Decode and publish RelaySMS payloads."""

import base64
import logging
import json

from src.grpc_publisher_client import publish_content
from src.bridge_server_grpc_client import publish_bridge_content
from src.utils import get_configs

logger = logging.getLogger(__name__)

DISABLE_BRIDGE_PAYLOADS_OVER_HTTP = (
    get_configs("DISABLE_BRIDGE_PAYLOADS_OVER_HTTP", default_value="false").lower()
    == "true"
)


def decode_and_publish(payload, request_origin=None):
    """Decodes and publishes the RelaySMS payload based on the request origin.

    Args:
        payload (str or dict): The incoming request payload containing the data.
        request_origin (str): The origin of the request, either 'http', 'smtp' or 'ftp'.

    Returns:
        tuple: A message and an error (if any).
    """

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None, "Invalid JSON format"

    encoded_content = payload.get("text")
    sender_id = payload.get("MSISDN") or payload.get("address")

    if not encoded_content:
        return None, "Missing required field: text"
    if not sender_id:
        return None, "Missing required field: address or MSISDN"

    try:
        decoded_bytes = base64.b64decode(encoded_content)
    except (ValueError, TypeError):
        return None, "Invalid Base64-encoded payload"

    is_bridge_request = decoded_bytes[0] == 0

    if (
        is_bridge_request
        and request_origin == "http"
        and DISABLE_BRIDGE_PAYLOADS_OVER_HTTP
    ):
        logger.warning("✖ Bridge payloads over HTTP are disabled.")
        return None, "Bridge payloads over HTTP are restricted."

    if is_bridge_request:
        bridge_content = base64.b64encode(decoded_bytes[1:]).decode("utf-8")
        publish_response, publish_error = publish_bridge_content(
            content=bridge_content, phone_number=sender_id
        )
    else:
        publish_response, publish_error = publish_content(
            content=encoded_content, sender=sender_id
        )

    if publish_error:
        logger.error("✖ gRPC error: %s", publish_error.code())
        return None, publish_error.details()

    if not publish_response.success:
        logger.error("✖ gRPC error: %s", publish_response.message)
        return None, publish_response.message

    logger.info(
        "✔ Payload published successfully from request origin: %s", request_origin
    )
    return (
        publish_response.message
        if is_bridge_request
        else publish_response.publisher_response
    ), None
