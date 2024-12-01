"""FTP Server Module"""

import os
import logging
from OpenSSL import SSL
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.servers import FTPServer
from pyftpdlib.handlers import FTPHandler, TLS_FTPHandler, TLS_DTPHandler
from src.payload_service import decode_and_publish

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("[FTP SERVER]")

FTP_USERNAME = os.environ["FTP_USERNAME"]
FTP_PASSWORD = os.environ["FTP_PASSWORD"]
FTP_IP_ADDRESS = os.environ["FTP_IP_ADDRESS"]
FTP_PORT = int(os.environ.get("FTP_PORT", 9909))
FTP_MAX_CON = int(os.environ.get("FTP_MAX_CON", 256))
FTP_MAX_CON_PER_IP = int(os.environ.get("FTP_MAX_CON_PER_IP", 5))
FTP_PASSIVE_PORTS = [int(p) for p in os.environ["FTP_PASSIVE_PORTS"].split("-")]
FTP_DIRECTORY = os.environ["FTP_DIRECTORY"]
SSL_CERTIFICATE = os.environ["SSL_CERTIFICATE"]
SSL_KEY = os.environ["SSL_KEY"]


def file_received(_, file):
    """Handle file received event.

    Args:
        _: Instance of FTPHandler (not used).
        file (str): The name of the received file.
    """
    try:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        publisher_response, err = decode_and_publish(content)

        if err:
            logger.error(err)
            os.remove(file)
            logger.info("Deleted file %s due to error", file)
            return

        logger.info({"publisher_response": publisher_response})
        os.remove(file)

    except Exception as exc:
        logger.error("Failed to process file '%s': %s", file, exc, exc_info=True)


def create_ssl_context(certfile, keyfile):
    """Create an SSL context.

    Args:
        certfile (str): Path to the SSL certificate file.
        keyfile (str): Path to the SSL private key file.

    Returns:
        SSLContext: SSL context.
    """
    context = SSL.Context(SSL.TLS_SERVER_METHOD)
    context.use_certificate_file(certfile)
    context.use_privatekey_file(keyfile)
    return context


def main():
    """
    Main function to start the FTP server.
    """
    if os.path.exists(SSL_CERTIFICATE) and os.path.exists(SSL_KEY):
        logger.info("SSL credentials found. Running in production mode.")
        ssl_context = create_ssl_context(SSL_CERTIFICATE, SSL_KEY)
        handler = TLS_FTPHandler
        handler.ssl_context = ssl_context
        handler.tls_control_required = True
        handler.tls_data_required = True
    else:
        logger.info("No valid SSL credentials found. Running in development mode.")
        handler = FTPHandler

    authorizer = DummyAuthorizer()
    authorizer.add_user(FTP_USERNAME, FTP_PASSWORD, FTP_DIRECTORY, perm="w")

    address = (FTP_IP_ADDRESS, FTP_PORT)
    server = FTPServer(address, handler)

    server.max_cons = FTP_MAX_CON
    server.max_cons_per_ip = FTP_MAX_CON_PER_IP

    dtp_handler = TLS_DTPHandler

    handler.authorizer = authorizer
    handler.banner = "SmsWithoutBorders FTP Server"
    handler.passive_ports = range(FTP_PASSIVE_PORTS[0], FTP_PASSIVE_PORTS[1])
    handler.permit_privileged_ports = True

    handler.on_file_received = file_received
    handler.dtp_handler = dtp_handler

    server.serve_forever()


if __name__ == "__main__":
    main()
