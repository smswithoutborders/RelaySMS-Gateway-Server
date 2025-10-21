"""Segment cache manager for v4 payload assembly."""

from typing import List, Tuple

from logutils import get_logger
from src.models import MessageSegments

logger = get_logger(__name__)


class SegmentCache:
    """Manages caching and assembly of message segments."""

    @staticmethod
    def store_segment(
        session_id: str,
        sender_id: str,
        segment_number: int,
        total_segments: int,
        image_length: int,
        text_length: int,
        content: bytes,
    ) -> bool:
        """Store a message segment in the cache.

        Args:
            session_id: Unique identifier for the message session.
            sender_id: Identifier of the sender.
            segment_number: Position of this segment in the sequence (0-indexed).
            total_segments: Total number of segments expected for this session.
            image_length: Length of image data in bytes.
            text_length: Length of text data in bytes.
            content: The actual content bytes (base64 payload).

        Returns:
            True if segment was stored successfully, False otherwise.

        Note:
            If a segment with the same session_id and segment_number already exists,
            it will be silently ignored (newer segments are dumped to handle retries).
        """
        try:
            existing = MessageSegments.get_or_none(
                (MessageSegments.session_id == session_id)
                & (MessageSegments.sender_id == sender_id)
                & (MessageSegments.segment_number == segment_number)
            )

            if existing:
                logger.debug(
                    "Segment already exists for session %s, segment %d. Ignoring duplicate.",
                    session_id,
                    segment_number,
                )
                return True

            MessageSegments.create(
                session_id=session_id,
                sender_id=sender_id,
                segment_number=segment_number,
                total_segments=total_segments,
                image_length=image_length,
                text_length=text_length,
                content=content,
            )

            logger.debug(
                "Stored segment %d/%d for session %s",
                segment_number,
                total_segments,
                session_id,
            )
            return True

        except Exception as e:
            logger.error("Failed to store segment: %s", str(e))
            return False

    @staticmethod
    def get_segments(session_id: str, sender_id: str) -> List[MessageSegments]:
        """Retrieve all segments for a given session and sender.

        Args:
            session_id: Unique identifier for the message session.
            sender_id: Identifier of the sender.

        Returns:
            List of MessageSegments ordered by segment_number.
        """
        try:
            segments = (
                MessageSegments.select()
                .where(
                    (MessageSegments.session_id == session_id)
                    & (MessageSegments.sender_id == sender_id)
                )
                .order_by(MessageSegments.segment_number)
            )
            return list(segments)
        except Exception as e:
            logger.error("Failed to retrieve segments: %s", str(e))
            return []

    @staticmethod
    def is_session_complete(session_id: str, sender_id: str) -> Tuple[bool, int, int]:
        """Check if all segments for a session from a specific sender have been received.

        Args:
            session_id: Unique identifier for the message session.
            sender_id: Identifier of the sender.

        Returns:
            Tuple of (is_complete, segments_received, total_segments_expected).
            is_complete is True when segments_received == total_segments_expected.
        """
        try:
            segments = (
                MessageSegments.select()
                .where(
                    (MessageSegments.session_id == session_id)
                    & (MessageSegments.sender_id == sender_id)
                )
                .order_by(MessageSegments.segment_number)
            )

            received_count = segments.count()

            if received_count == 0:
                return False, 0, 0

            first_segment = segments.first()
            total_expected = first_segment.total_segments

            is_complete = received_count == total_expected

            logger.debug(
                "Session %s from sender %s: %d/%d segments received (complete=%s)",
                session_id,
                sender_id,
                received_count,
                total_expected,
                is_complete,
            )

            return is_complete, received_count, total_expected

        except Exception as e:
            logger.error("Failed to check session completeness: %s", str(e))
            return False, 0, 0

    @staticmethod
    def delete_session(session_id: str, sender_id: str) -> int:
        """Delete all segments for a given session and sender.

        Args:
            session_id: Unique identifier for the message session.
            sender_id: Identifier of the sender.

        Returns:
            Number of segments deleted.
        """
        try:
            deleted_count = (
                MessageSegments.delete()
                .where(
                    (MessageSegments.session_id == session_id)
                    & (MessageSegments.sender_id == sender_id)
                )
                .execute()
            )
            logger.debug(
                "Deleted %d segments for session %s from sender %s",
                deleted_count,
                session_id,
                sender_id,
            )
            return deleted_count
        except Exception as e:
            logger.error("Failed to delete session: %s", str(e))
            return 0
