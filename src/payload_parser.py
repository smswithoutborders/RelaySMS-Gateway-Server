# SPDX-License-Identifier: GPL-3.0-only
"""Payload parser for handling segmented messages with metadata."""

import base64
import struct
from typing import Tuple, Optional, Dict
from logutils import get_logger

logger = get_logger(__name__)

BRIDGE_REQUEST_IDENTIFIER = 0
MAX_SEGMENTS = 255


class PayloadParser:
    """Parser for payload format."""

    @staticmethod
    def is_bridge_payload(payload: str) -> bool:
        """Detect if a payload is in bridge format.

        Bridge payloads are base64-encoded and start with a zero byte.

        Args:
            payload: The base64-encoded payload string.
        Returns:
            True if the payload is a bridge request, False otherwise.
        """
        try:
            decoded_bytes = base64.b64decode(payload)
            return (
                len(decoded_bytes) > 0 and decoded_bytes[0] == BRIDGE_REQUEST_IDENTIFIER
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def is_it_payload(payload: str) -> bool:
        """Detect if a payload is in image-text format.

        Image-text (IT) payloads start with base64-encoded metadata with a "4" prefix:
        - Short format: indicator(4)[1B] + session_id(1B) + segment_number(1B)
        - Long format: indicator(4)[1B] + session_id(1B) + segment_number(1B)
            + total_segments(1B) + image_length(2B) + text_length(2B)

        Args:
            payload: The payload string to check.

        Returns:
            True if the payload appears to be IT format, False otherwise.
        """
        if len(payload) < 4:
            return False

        try:
            metadata_b64 = payload[:4]
            metadata_bytes = base64.b64decode(metadata_b64)
            if len(metadata_bytes) == 3 and metadata_bytes[0] == 4:
                return True
        except (ValueError, TypeError):
            pass

        return False

    @staticmethod
    def parse_image_text_metadata(metadata_bytes: bytes) -> Optional[Dict]:
        """Parse the image-text metadata from bytes.

        Args:
            metadata_bytes: The metadata bytes to parse.

        Returns:
            Dict with parsed metadata fields or None if parsing fails.
        """
        if len(metadata_bytes) not in [3, 8]:
            logger.error(
                "Invalid metadata length: expected 3 or 8, got %d", len(metadata_bytes)
            )
            return None

        _ = metadata_bytes[0]
        session_id = metadata_bytes[1]
        segment_number = metadata_bytes[2]
        total_segments = 0
        text_length = 0
        image_length = 0

        if len(metadata_bytes) == 8 and segment_number == 0:
            total_segments = metadata_bytes[3]

            if total_segments == 0:
                logger.error("Total segments cannot be zero.")
                return None

            image_length = struct.unpack("<H", metadata_bytes[4:6])[0]
            text_length = struct.unpack("<H", metadata_bytes[6:8])[0]

        metadata = {
            "session_id": session_id,
            "segment_number": segment_number,
            "total_segments": total_segments,
        }

        metadata["image_length"] = image_length
        metadata["text_length"] = text_length

        logger.debug("Parsed metadata: %s", metadata)
        return metadata

    @staticmethod
    def parse_image_text_payload(payload: str) -> Optional[Tuple[Dict, str]]:
        """Parse a complete image-text payload into metadata and content.

        Returns:
            Tuple of (metadata_dict, content_string) or None if parsing fails.
        """
        try:
            try:
                metadata_b64 = payload[:4]
                metadata_bytes = base64.b64decode(metadata_b64)
                segment_number = metadata_bytes[2]
                if segment_number > 0:
                    content = payload[4:]
                else:
                    metadata_b64 = payload[:12]
                    metadata_bytes = base64.b64decode(metadata_b64)
                    content = payload[12:]
            except (ValueError, TypeError):
                logger.error("Failed to parse image-text payload: invalid base64")
                return None

            metadata = PayloadParser.parse_image_text_metadata(metadata_bytes)

            if metadata is None:
                return None

            if not content:
                logger.warning("Payload has no content after metadata")
                return None

            logger.debug(
                "Parsed payload: session_id=%d, segment=%d/%d, content_length=%d",
                metadata["session_id"],
                metadata["segment_number"] + 1,
                metadata["total_segments"],
                len(content),
            )

            return metadata, content

        except Exception as e:
            logger.error("Failed to parse image-text payload: %s", str(e))
            return None
