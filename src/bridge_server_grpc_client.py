"""Bridge Server gRPC Client."""

import functools
import grpc

import bridge_pb2
import bridge_pb2_grpc

from src.utils import get_configs
from logutils import get_logger

logger = get_logger(__name__)


def get_channel():
    """Get the appropriate gRPC channel based on the mode.

    Returns:
        grpc.Channel: The gRPC channel.
    """
    mode = get_configs("MODE", default_value="development")
    hostname = get_configs("BRIDGE_GRPC_HOST")
    port = get_configs("BRIDGE_GRPC_PORT")
    secure_port = get_configs("BRIDGE_GRPC_SSL_PORT")

    if mode == "production":
        logger.info("Connecting to bridge gRPC server at %s:%s", hostname, secure_port)
        credentials = grpc.ssl_channel_credentials()
        logger.info("Using secure channel for gRPC communication")
        return grpc.secure_channel(f"{hostname}:{secure_port}", credentials)

    logger.info("Connecting to bridge gRPC server at %s:%s", hostname, port)
    logger.warning("Using insecure channel for gRPC communication")
    return grpc.insecure_channel(f"{hostname}:{port}")


def grpc_call():
    """Decorator to handle gRPC calls."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                channel = get_channel()

                with channel as conn:
                    kwargs["stub"] = bridge_pb2_grpc.EntityServiceStub(conn)
                    return func(*args, **kwargs)
            except grpc.RpcError as e:
                return None, e
            except Exception as e:
                raise e

        return wrapper

    return decorator


@grpc_call()
def publish_bridge_content(content, phone_number, **kwargs):
    """
    Publishes bridge content.

    Args:
        content (str): The content to be published.
        phone_number (str): The phone number associated with the bridge entity.
        **kwargs:
            - stub (object): The gRPC client stub for making requests.

    Returns:
        tuple:
            - response (object): The bridge server's response.
            - error (Exception or None): None if successful, otherwise the encountered exception.
    """
    stub = kwargs["stub"]
    image_length = kwargs.get("image_length")

    request = bridge_pb2.PublishContentRequest(
        content=content,
        metadata={
            "From": phone_number,
            "Image-Length": str(image_length) if image_length else "",
        },
    )
    response = stub.PublishContent(request)
    logger.info("Content published successfully.")
    return response, None
