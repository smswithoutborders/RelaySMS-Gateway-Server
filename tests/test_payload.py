"""Tests for payload_service.py."""

from unittest.mock import Mock, patch
import base64
import json
import struct
import pytest


from src.payload_service import (
    decode_and_publish,
    BRIDGE_REQUEST_IDENTIFIER,
    detect_payload_type,
    _assemble_complete_payload,
)
from src.payload_parser import PayloadParser
from src.models import MessageSegments
from src.segment_cache import SegmentCache


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


class TestITPayload:
    """Test Image-Text (IT) payload parsing functionality."""

    @staticmethod
    def _create_it_payload_short(
        session_id: int, segment_number: int, content: str = ""
    ) -> str:
        """Create short form IT payload using struct.pack.

        Args:
            session_id: Session identifier (1 byte)
            segment_number: Segment number (1 byte)
            content: Optional content to append

        Returns:
            Base64-encoded IT payload string
        """
        metadata_bytes = struct.pack("BBB", 4, session_id, segment_number)
        metadata_b64 = base64.b64encode(metadata_bytes).decode()
        return metadata_b64 + content

    @staticmethod
    def _create_it_payload_long(
        session_id: int,
        segment_number: int,
        total_segments: int,
        image_length: int,
        text_length: int,
        content: str = "",
    ) -> str:
        """Create long form IT payload using struct.pack.

        Args:
            session_id: Session identifier (1 byte)
            segment_number: Segment number (1 byte)
            total_segments: Total segments (1 byte)
            image_length: Image length (2 bytes, little endian)
            text_length: Text length (2 bytes, little endian)
            content: Optional content to append

        Returns:
            Base64-encoded IT payload string
        """
        metadata_bytes = struct.pack(
            "<BBBBHH",
            4,
            session_id,
            segment_number,
            total_segments,
            image_length,
            text_length,
        )
        metadata_b64 = base64.b64encode(metadata_bytes).decode()
        return metadata_b64 + content

    @pytest.mark.parametrize(
        "payload, expected_type",
        [
            ("_create_it_payload_long", "image-text"),
            ("_create_it_payload_short", "image-text"),
            (base64.b64encode(b"regular content").decode(), "platform"),
            (base64.b64encode(b"\x00bridge").decode(), "bridge"),
        ],
    )
    def test_payload_type_detection(self, payload, expected_type):
        """Test that different payload types are correctly detected."""
        if payload == "_create_it_payload_long":
            payload = self._create_it_payload_long(
                42, 0, 1, 50, 30, base64.b64encode(b"content").decode()
            )
        elif payload == "_create_it_payload_short":
            payload = self._create_it_payload_short(
                42, 1, base64.b64encode(b"subsequent").decode()
            )

        assert detect_payload_type(payload) == expected_type

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            "BAD",
            base64.b64encode(b"\x05\x2a\x01").decode(),
            "invalid_base64!@#",
        ],
    )
    def test_invalid_it_payload_format(self, invalid_payload):
        """Test that invalid IT format is rejected."""
        assert detect_payload_type(invalid_payload) == "platform"

    @pytest.mark.parametrize(
        "metadata_bytes, expected",
        [
            (
                struct.pack("<BBBBHH", 4, 255, 0, 15, 65535, 65535),
                {
                    "session_id": 255,
                    "segment_number": 0,
                    "total_segments": 15,
                    "image_length": 65535,
                    "text_length": 65535,
                },
            ),
            (
                struct.pack("BBB", 4, 42, 1),
                {
                    "session_id": 42,
                    "segment_number": 1,
                    "total_segments": 0,
                    "image_length": 0,
                    "text_length": 0,
                },
            ),
            (
                struct.pack("BBB", 4, 10, 2),
                {
                    "session_id": 10,
                    "segment_number": 2,
                    "total_segments": 0,
                    "image_length": 0,
                    "text_length": 0,
                },
            ),
            (
                struct.pack("BBB", 4, 255, 1),
                {
                    "session_id": 255,
                    "segment_number": 1,
                    "total_segments": 0,
                    "image_length": 0,
                    "text_length": 0,
                },
            ),
        ],
    )
    def test_parse_it_metadata(self, metadata_bytes, expected):
        """Test parsing of IT payload metadata."""
        result = PayloadParser.parse_image_text_metadata(metadata_bytes)
        assert result is not None
        assert result == expected

    def test_parse_it_payload_complete(self):
        """Test parsing complete IT payload for long form."""
        content = base64.b64encode(b"test_content").decode()
        payload = self._create_it_payload_long(42, 0, 1, 50, 30, content)
        result = PayloadParser.parse_image_text_payload(payload)

        assert result is not None
        metadata, parsed_content = result
        assert metadata["session_id"] == 42
        assert metadata["segment_number"] == 0
        assert metadata["total_segments"] == 1
        assert metadata["image_length"] == 50
        assert metadata["text_length"] == 30
        assert content in parsed_content

    def test_parse_it_payload_subsequent_segment(self):
        """Test parsing complete IT payload for short form."""
        content = base64.b64encode(b"second_segment").decode()
        payload = self._create_it_payload_short(42, 1, content)
        result = PayloadParser.parse_image_text_payload(payload)

        assert result is not None
        metadata, parsed_content = result
        assert metadata["session_id"] == 42
        assert metadata["segment_number"] == 1
        assert metadata["total_segments"] == 0
        assert metadata["image_length"] == 0
        assert metadata["text_length"] == 0
        assert content in parsed_content

    @pytest.mark.parametrize(
        "invalid_metadata",
        [
            struct.pack("<BBBBHH", 4, 10, 0, 0, 100, 50),
            b"\x04\x10",
            b"\x04",
            b"\x04\x10\x05\x03\x64",
        ],
    )
    def test_invalid_segment_numbers(self, invalid_metadata):
        """Test that invalid segment configurations are rejected."""
        assert PayloadParser.parse_image_text_metadata(invalid_metadata) is None

    @pytest.fixture(autouse=True)
    def cleanup_segments(self):
        """Cleanup message segments before and after tests."""
        MessageSegments.delete().execute()
        yield
        MessageSegments.delete().execute()

    def test_single_segment_assembly(self):
        """Test assembling a complete payload from a single segment."""

        session_id = "1000"
        sender_id = "+1234567890"
        content = base64.b64encode(b"complete_payload").decode()

        SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=1,
            image_length=100,
            text_length=50,
            content=content.encode(),
        )

        result = _assemble_complete_payload(session_id, sender_id)

        assert result is not None
        assembled_content, image_length = result
        assert assembled_content == content
        assert image_length == 100

    def test_multi_segment_assembly_ordered(self):
        """Test assembling payload from multiple segments in order."""

        session_id = "1001"
        sender_id = "+1234567890"

        for i in range(3):
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"part{i}".encode(),
            )

        result = _assemble_complete_payload(session_id, sender_id)

        assert result is not None
        assembled_content, image_length = result
        assert assembled_content == "part0part1part2"
        assert image_length == 100

    def test_multi_segment_assembly_unordered(self):
        """Test assembling payload from segments received out of order."""

        session_id = "1002"
        sender_id = "+1234567890"

        segments_data = [
            (2, "LAST"),
            (0, "FIRST"),
            (1, "MIDDLE"),
        ]

        for seg_num, content in segments_data:
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=seg_num,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=content.encode(),
            )

        result = _assemble_complete_payload(session_id, sender_id)

        assert result is not None
        assembled_content, image_length = result
        assert assembled_content == "FIRSTMIDDLELAST"
        assert image_length == 100

    def test_assembly_with_missing_segments(self):
        """Test that assembly works with available segments even if some are missing."""

        session_id = "1003"
        sender_id = "+1234567890"

        SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=3,
            image_length=100,
            text_length=50,
            content=b"segment0",
        )

        SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=2,
            total_segments=3,
            image_length=100,
            text_length=50,
            content=b"segment2",
        )

        result = _assemble_complete_payload(session_id, sender_id)

        assert result is not None
        assembled_content, image_length = result
        assert assembled_content == "segment0segment2"
        assert image_length == 100

    def test_assembly_empty_session(self):
        """Test assembly fails gracefully for non-existent session."""

        assembled = _assemble_complete_payload("nonexistent_session", "+0000000000")
        assert assembled is None

    @patch("src.payload_service.publish_content")
    def test_it_payload_end_to_end_single_segment(self, mock_publish):
        """Test end-to-end IT payload processing with single segment."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.publisher_response = "Published"
        mock_publish.return_value = (mock_response, None)

        platform_content = base64.b64encode(b"platform_message").decode()
        it_payload = self._create_it_payload_long(42, 0, 1, 50, 30, platform_content)

        payload = {
            "text": it_payload,
            "address": "+1234567890",
            "date": 1633024800000,
            "date_sent": 1633024800000,
        }

        result, error = decode_and_publish(payload, "http")

        assert error is None
        assert result == "Published"
        mock_publish.assert_called_once()

    @patch("src.payload_service.publish_content")
    def test_it_payload_end_to_end_multi_segment(self, mock_publish):
        """Test end-to-end IT payload processing with multiple segments."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.publisher_response = "Published"
        mock_publish.return_value = (mock_response, None)

        session_id = 50
        sender = "+1234567890"

        for seg_num in range(3):
            segment_content = f"seg{seg_num}"

            if seg_num == 0:
                it_payload = self._create_it_payload_long(
                    session_id, seg_num, 3, 100, 50, segment_content
                )
            else:
                it_payload = self._create_it_payload_short(
                    session_id, seg_num, segment_content
                )

            payload = {
                "text": it_payload,
                "address": sender,
                "date": 1633024800000,
                "date_sent": 1633024800000,
            }

            result, error = decode_and_publish(payload, "http")

            if seg_num < 2:
                assert error is None
                assert "Segment" in result and "received and cached" in result
                assert mock_publish.call_count == 0
            else:
                assert error is None
                assert result == "Published"
                mock_publish.assert_called_once()

        segments = SegmentCache.get_segments(str(session_id), sender)
        assert len(segments) == 0

    @patch("src.payload_service.publish_bridge_content")
    def test_it_payload_containing_bridge_content(self, mock_publish):
        """Test IT payload that contains bridge content after assembly."""
        mock_response = Mock()
        mock_response.success = True
        mock_response.message = "Bridge published"
        mock_publish.return_value = (mock_response, None)

        bridge_content = bytes([BRIDGE_REQUEST_IDENTIFIER]) + b"bridge_data"
        bridge_b64 = base64.b64encode(bridge_content).decode()

        it_payload = self._create_it_payload_long(42, 0, 1, 50, 30, bridge_b64)

        payload = {
            "text": it_payload,
            "address": "+1234567890",
            "date": 1633024800000,
            "date_sent": 1633024800000,
        }

        result, error = decode_and_publish(payload, "smtp")

        assert error is None
        assert result == "Bridge published"
        mock_publish.assert_called_once()

    def test_it_payload_assembly_failure_cleanup(self):
        """Test that failed assembly cleans up cached segments."""

        session_id = "1004"
        sender_id = "+1234567890"

        SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=1,
            image_length=100,
            text_length=50,
            content=b"test",
        )

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 1

        SegmentCache.delete_session(session_id, sender_id)
        assembled = _assemble_complete_payload(session_id, sender_id)
        assert assembled is None


class TestSegmentCache:
    """Test segment caching functionality."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup and teardown for each test."""

        MessageSegments.delete().execute()
        yield
        MessageSegments.delete().execute()

    def test_store_single_segment(self):
        """Test storing a single segment."""

        session_id = "100"
        sender_id = "+1234567890"

        success = SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=1,
            image_length=100,
            text_length=50,
            content=b"test_content",
        )

        assert success is True

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 1
        assert segments[0].session_id == "100"
        assert segments[0].sender_id == "+1234567890"
        assert segments[0].segment_number == 0
        assert segments[0].total_segments == 1
        assert segments[0].content == b"test_content"

    def test_store_multiple_segments(self):
        """Test storing multiple segments for the same session."""

        session_id = "200"
        sender_id = "+1234567890"

        for i in range(3):
            success = SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"segment_{i}".encode(),
            )
            assert success is True

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 3
        assert segments[0].content == b"segment_0"
        assert segments[1].content == b"segment_1"
        assert segments[2].content == b"segment_2"

    def test_duplicate_segment_ignored(self):
        """Test that duplicate segments are ignored."""

        session_id = "300"
        sender_id = "+1234567890"

        success1 = SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=2,
            image_length=100,
            text_length=50,
            content=b"first_content",
        )
        assert success1 is True

        success2 = SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=2,
            image_length=100,
            text_length=50,
            content=b"duplicate_content",
        )
        assert success2 is True

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 1
        assert segments[0].content == b"first_content"

    def test_is_session_complete_single_segment(self):
        """Test session completeness check for single segment."""

        session_id = "400"
        sender_id = "+1234567890"

        SegmentCache.store_segment(
            session_id=session_id,
            sender_id=sender_id,
            segment_number=0,
            total_segments=1,
            image_length=100,
            text_length=50,
            content=b"content",
        )

        is_complete, received, total = SegmentCache.is_session_complete(
            session_id, sender_id
        )
        assert is_complete is True
        assert received == 1
        assert total == 1

    def test_is_session_complete_partial(self):
        """Test session completeness check for partial segments."""

        session_id = "500"
        sender_id = "+1234567890"

        for i in range(2):
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"segment_{i}".encode(),
            )

        is_complete, received, total = SegmentCache.is_session_complete(
            session_id, sender_id
        )
        assert is_complete is False
        assert received == 2
        assert total == 3

    def test_is_session_complete_all_segments(self):
        """Test session completeness when all segments received."""

        session_id = "600"
        sender_id = "+1234567890"

        for i in range(3):
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"segment_{i}".encode(),
            )

        is_complete, received, total = SegmentCache.is_session_complete(
            session_id, sender_id
        )
        assert is_complete is True
        assert received == 3
        assert total == 3

    def test_is_session_complete_nonexistent(self):
        """Test session completeness check for non-existent session."""

        is_complete, received, total = SegmentCache.is_session_complete(
            "999", "+0000000000"
        )
        assert is_complete is False
        assert received == 0
        assert total == 0

    def test_delete_session(self):
        """Test deleting all segments for a session."""

        session_id = "700"
        sender_id = "+1234567890"

        for i in range(3):
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"segment_{i}".encode(),
            )

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 3

        deleted_count = SegmentCache.delete_session(session_id, sender_id)
        assert deleted_count == 3

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 0

    def test_delete_nonexistent_session(self):
        """Test deleting a non-existent session."""

        deleted_count = SegmentCache.delete_session("999", "+0000000000")
        assert deleted_count == 0

    def test_segments_ordered_by_segment_number(self):
        """Test that segments are retrieved in correct order."""

        session_id = "800"
        sender_id = "+1234567890"

        for i in [2, 0, 1]:
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"segment_{i}".encode(),
            )

        segments = SegmentCache.get_segments(session_id, sender_id)
        assert len(segments) == 3
        assert segments[0].segment_number == 0
        assert segments[1].segment_number == 1
        assert segments[2].segment_number == 2

    def test_multiple_sessions_isolated(self):
        """Test that segments from different sessions are isolated."""

        sender_a = "+1111111111"
        sender_b = "+2222222222"

        for i in range(2):
            SegmentCache.store_segment(
                session_id="A",
                sender_id=sender_a,
                segment_number=i,
                total_segments=2,
                image_length=100,
                text_length=50,
                content=f"session_A_{i}".encode(),
            )

        for i in range(3):
            SegmentCache.store_segment(
                session_id="B",
                sender_id=sender_b,
                segment_number=i,
                total_segments=3,
                image_length=100,
                text_length=50,
                content=f"session_B_{i}".encode(),
            )

        segments_a = SegmentCache.get_segments("A", sender_a)
        assert len(segments_a) == 2
        assert all(seg.session_id == "A" for seg in segments_a)

        segments_b = SegmentCache.get_segments("B", sender_b)
        assert len(segments_b) == 3
        assert all(seg.session_id == "B" for seg in segments_b)

        SegmentCache.delete_session("A", sender_a)

        assert len(SegmentCache.get_segments("A", sender_a)) == 0
        assert len(SegmentCache.get_segments("B", sender_b)) == 3

    def test_same_session_different_senders_isolated(self):
        """Test that same session_id and segment_number from different senders are isolated."""

        session_id = "shared_session_100"
        sender_1 = "+1111111111"
        sender_2 = "+2222222222"

        for i in range(2):
            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_1,
                segment_number=i,
                total_segments=2,
                image_length=100,
                text_length=50,
                content=f"sender1_segment_{i}".encode(),
            )

            SegmentCache.store_segment(
                session_id=session_id,
                sender_id=sender_2,
                segment_number=i,
                total_segments=2,
                image_length=100,
                text_length=50,
                content=f"sender2_segment_{i}".encode(),
            )

        segments_1 = SegmentCache.get_segments(session_id, sender_1)
        assert len(segments_1) == 2
        assert all(seg.sender_id == sender_1 for seg in segments_1)
        assert segments_1[0].content == b"sender1_segment_0"
        assert segments_1[1].content == b"sender1_segment_1"

        segments_2 = SegmentCache.get_segments(session_id, sender_2)
        assert len(segments_2) == 2
        assert all(seg.sender_id == sender_2 for seg in segments_2)
        assert segments_2[0].content == b"sender2_segment_0"
        assert segments_2[1].content == b"sender2_segment_1"

        is_complete_1, received_1, total_1 = SegmentCache.is_session_complete(
            session_id, sender_1
        )
        assert is_complete_1 is True
        assert received_1 == 2
        assert total_1 == 2

        is_complete_2, received_2, total_2 = SegmentCache.is_session_complete(
            session_id, sender_2
        )
        assert is_complete_2 is True
        assert received_2 == 2
        assert total_2 == 2

        deleted_1 = SegmentCache.delete_session(session_id, sender_1)
        assert deleted_1 == 2

        assert len(SegmentCache.get_segments(session_id, sender_1)) == 0
        assert len(SegmentCache.get_segments(session_id, sender_2)) == 2
