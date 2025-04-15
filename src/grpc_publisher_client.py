"""Publisher gRPC Client"""

import functools
import grpc

import publisher_pb2
import publisher_pb2_grpc

from src.utils import get_configs
from logutils import get_logger

logger = get_logger(__name__)


def get_channel():
    """Get the appropriate gRPC channel based on the mode.

    Returns:
        grpc.Channel: The gRPC channel.
    """
    mode = get_configs("MODE", default_value="development")
    hostname = get_configs("PUBLISHER_GRPC_HOST")
    port = get_configs("PUBLISHER_GRPC_PORT")
    secure_port = get_configs("PUBLISHER_GRPC_SSL_PORT")

    if mode == "production":
        logger.info(
            "Connecting to publisher gRPC server at %s:%s", hostname, secure_port
        )
        credentials = grpc.ssl_channel_credentials()
        logger.info("Using secure channel for gRPC communication")
        return grpc.secure_channel(f"{hostname}:{secure_port}", credentials)

    logger.info("Connecting to publisher gRPC server at %s:%s", hostname, port)
    logger.warning("Using insecure channel for gRPC communication")
    return grpc.insecure_channel(f"{hostname}:{port}")


def grpc_call(func):
    """Decorator to handle gRPC calls."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            channel = get_channel()

            with channel as conn:
                kwargs["stub"] = publisher_pb2_grpc.PublisherStub(conn)
                return func(*args, **kwargs)
        except grpc.RpcError as e:
            return None, e
        except Exception as e:
            raise e

    return wrapper


@grpc_call
def publish_content(content, sender, **kwargs):
    """Request for publishing message to a target platform"""
    stub = kwargs["stub"]
    date = kwargs["date"]
    date_sent = kwargs["date_sent"]
    request = publisher_pb2.PublishContentRequest(
        content=content,
        metadata={
            "From": sender,
            "Date": date,
            "Date_sent": date_sent,
        },
    )

    response = stub.PublishContent(request)
    return response, None
