"""Module to listen for incoming emails via IMAP, process them, and publish encrypted data."""

import os
import ssl
import logging

import time
import socket
import imaplib
import traceback

from imap_tools import (
    AND,
    MailBox,
    MailboxLoginError,
    MailboxLogoutError,
)
from email_reply_parser import EmailReplyParser
from src.payload_service import decode_and_publish

IMAP_SERVER = os.environ["IMAP_SERVER"]
IMAP_PORT = int(os.environ.get("IMAP_PORT", 993))
IMAP_USERNAME = os.environ["IMAP_USERNAME"]
IMAP_PASSWORD = os.environ["IMAP_PASSWORD"]
MAIL_FOLDER = os.environ.get("MAIL_FOLDER", "INBOX")
SSL_CERTIFICATE = os.environ["SSL_CERTIFICATE"]
SSL_KEY = os.environ["SSL_KEY"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("[IMAP LISTENER]")


def delete_email(mailbox, email_uid):
    """
    Delete an email from the mailbox.

    Args:
        mailbox (imaplib.IMAP4_SSL): An IMAP4_SSL object representing the
            connection to the IMAP server.
        email_uid (int): The UID of the email to be deleted.

    Raises:
        Exception: If there's an error while deleting the email.
    """
    try:
        if email_uid:
            mailbox.delete(email_uid)
            logger.info("Successfully deleted email %s", email_uid)
    except Exception as e:
        logger.error("Error deleting email %s: %s", email_uid, e)
        raise


def process_incoming_email(mailbox, email):
    """
    Process an incoming email.

    Args:
        mailbox (imaplib.IMAP4_SSL): An IMAP4_SSL object representing the connection
            to the IMAP server.
        email (imap_tools.MailMessage): An object representing the email message.
    """

    body = EmailReplyParser.parse_reply(email.text)
    email_uid = email.uid

    try:
        publisher_response, err = decode_and_publish(body)

        if err:
            logger.error(err)
            delete_email(mailbox, email_uid)
            return

        logger.info({"publisher_response": publisher_response})
        delete_email(mailbox, email_uid)

    except Exception as e:
        logger.error("Error processing email %s: %s", email_uid, e)


def main():
    """
    Main function to run the email processing loop.
    """
    ssl_context = ssl.create_default_context()
    ssl_context.load_cert_chain(certfile=SSL_CERTIFICATE, keyfile=SSL_KEY)

    done = False
    while not done:
        connection_start_time = time.monotonic()
        connection_live_time = 0.0
        try:
            with MailBox(IMAP_SERVER, IMAP_PORT, ssl_context=ssl_context).login(
                IMAP_USERNAME, IMAP_PASSWORD, MAIL_FOLDER
            ) as mailbox:
                logger.info(
                    "Connected to mailbox %s on %s", IMAP_SERVER, time.asctime()
                )
                while connection_live_time < 29 * 60:
                    try:
                        responses = mailbox.idle.wait(timeout=20)
                        if responses:
                            logger.debug("IMAP IDLE responses: %s", responses)

                        for msg in mailbox.fetch(
                            criteria=AND(seen=False),
                            bulk=50,
                            mark_seen=False,
                        ):
                            process_incoming_email(mailbox, msg)

                    except KeyboardInterrupt:
                        logger.info("Received KeyboardInterrupt, exiting...")
                        done = True
                        break
                    connection_live_time = time.monotonic() - connection_start_time
        except (
            TimeoutError,
            ConnectionError,
            imaplib.IMAP4.abort,
            MailboxLoginError,
            MailboxLogoutError,
            socket.herror,
            socket.gaierror,
            socket.timeout,
        ) as e:
            logger.error("Error occurred: %s", e)
            logger.error(traceback.format_exc())
            logger.info("Reconnecting in a minute...")
            time.sleep(60)


if __name__ == "__main__":
    main()
