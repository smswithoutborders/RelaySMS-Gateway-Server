"""Payload parser for handling segmented messages with metadata."""

import base64
import struct
from typing import Tuple, Optional, Dict
from logutils import get_logger

logger = get_logger(__name__)

BRIDGE_REQUEST_IDENTIFIER = 0
MAX_SEGMENTS = 15


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
            return decoded_bytes and decoded_bytes[0] == BRIDGE_REQUEST_IDENTIFIER
        except (ValueError, TypeError):
            return False

    @staticmethod
    def is_it_payload(payload: str) -> bool:
        """Detect if a payload is in image-text format.

        Image-text (IT) payloads start with hex-encoded metadata with a "04" prefix:
        - Short format: "04" + 4 hex chars (2 bytes: session_id + seg_info)
        - Long format: "04" + 12 hex chars (6 bytes: session_id + seg_info + image_length + text_length)

        Args:
            payload: The payload string to check.

        Returns:
            True if the payload appears to be IT format, False otherwise.
        """
        try:
            if len(payload) < 6:
                return False

            # Check prefix byte (should be 0x04)
            prefix_hex = payload[:2]
            prefix_byte = bytes.fromhex(prefix_hex)[0]

            if prefix_byte != 4:
                return False

            # Try to parse as short format (6 total hex chars: 2 prefix + 4 metadata)
            if len(payload) >= 6:
                try:
                    metadata_hex = payload[2:6]
                    metadata_bytes = bytes.fromhex(metadata_hex)
                    if len(metadata_bytes) == 2:
                        return True
                except (ValueError, TypeError):
                    pass

            # Try to parse as long format (14 total hex chars: 2 prefix + 12 metadata)
            if len(payload) >= 14:
                try:
                    metadata_hex = payload[2:14]
                    metadata_bytes = bytes.fromhex(metadata_hex)
                    if len(metadata_bytes) == 6:
                        return True
                except (ValueError, TypeError):
                    pass

            return False

        except (ValueError, TypeError, IndexError):
            return False

    @staticmethod
    def parse_image_text_metadata(metadata_hex: str) -> Optional[Dict]:
        """Parse the image-text metadata from hex string.

        Args:
            metadata_hex: Hex string containing metadata.
                - 12 characters (6 bytes) for long form with image/text lengths
                - 4 characters (2 bytes) for short form without image/text lengths

        Returns:
            Dict with parsed metadata fields or None if parsing fails.
        """
        if len(metadata_hex) not in [4, 12]:
            logger.error(
                "Invalid metadata length: expected 4 or 12, got %d", len(metadata_hex)
            )
            return None

        try:
            metadata_bytes = bytes.fromhex(metadata_hex)
            session_id = metadata_bytes[0]
            seg_info = metadata_bytes[1]
            segment_number = (seg_info >> 4) & 0x0F
            total_segments = seg_info & 0x0F

            if segment_number >= MAX_SEGMENTS or total_segments > MAX_SEGMENTS:
                logger.error(
                    "Invalid segment numbers: segment=%d, total=%d (max=%d)",
                    segment_number,
                    total_segments,
                    MAX_SEGMENTS,
                )
                return None

            if total_segments == 0:
                logger.error("Invalid total_segments: cannot be 0")
                return None

            if segment_number >= total_segments:
                logger.error(
                    "Invalid segment_number %d >= total_segments %d",
                    segment_number,
                    total_segments,
                )
                return None

            metadata = {
                "session_id": session_id,
                "segment_number": segment_number,
                "total_segments": total_segments,
            }

            if len(metadata_bytes) == 6:
                image_length = struct.unpack(">H", metadata_bytes[2:4])[0]
                text_length = struct.unpack(">H", metadata_bytes[4:6])[0]
                metadata["image_length"] = image_length
                metadata["text_length"] = text_length
            else:
                metadata["image_length"] = 0
                metadata["text_length"] = 0

            logger.debug("Parsed metadata: %s", metadata)
            return metadata

        except (ValueError, struct.error) as e:
            logger.error("Failed to parse metadata: %s", str(e))
            return None

    @staticmethod
    def parse_image_text_payload(payload: str) -> Optional[Tuple[Dict, str]]:
        """Parse a complete image-text payload into metadata and content.

        Args:
            payload: The full image-text payload string (prefix + metadata + content).
                Format: "04" + metadata_hex + content
                - Short format: "04" + 4 chars metadata = 6 chars total
                - Long format: "04" + 12 chars metadata = 14 chars total

        Returns:
            Tuple of (metadata_dict, content_string) or None if parsing fails.
        """
        if not PayloadParser.is_it_payload(payload):
            logger.error("Payload is not in image-text format")
            return None

        try:
            # Determine metadata length by trying long format first, then short format
            metadata_hex = None
            content = None

            # Try long format (12 hex chars)
            if len(payload) >= 14:
                try:
                    test_metadata = payload[2:14]
                    test_bytes = bytes.fromhex(test_metadata)
                    if len(test_bytes) == 6:
                        # Check if remaining content is valid base64 or hex
                        remaining = payload[14:]
                        if remaining:
                            metadata_hex = test_metadata
                            content = remaining
                except (ValueError, TypeError):
                    pass

            # Try short format (4 hex chars) if long format didn't work
            if metadata_hex is None and len(payload) >= 6:
                try:
                    test_metadata = payload[2:6]
                    test_bytes = bytes.fromhex(test_metadata)
                    if len(test_bytes) == 2:
                        remaining = payload[6:]
                        if remaining:
                            metadata_hex = test_metadata
                            content = remaining
                except (ValueError, TypeError):
                    pass

            if metadata_hex is None:
                logger.error("Could not determine metadata format")
                return None

            metadata = PayloadParser.parse_image_text_metadata(metadata_hex)

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
