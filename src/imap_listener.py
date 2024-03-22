import os
import imaplib
import logging
import email
import time

# TODO from concurrent.futures import ThreadPoolExecutor

from src.process_incoming_messages import process_data
from src import publisher

from src.users import Users
from src.users_entity import UsersEntity

from SwobBackendPublisher import Lib

IMAP_SERVER = os.environ["IMAP_SERVER"]
IMAP_PORT = os.environ.get("IMAP_PORT") or 993
IMAP_USERNAME = os.environ["IMAP_USERNAME"]
IMAP_PASSWORD = os.environ["IMAP_PASSWORD"]
MAIL_FOLDER = os.environ.get("MAIL_FOLDER") or "INBOX"


HOST = os.environ.get("HOST")
SOCK_PORT = os.environ.get("SOCK_PORT")
RSA_PR_KEY = os.environ.get("RSA_PR_KEY")
SHARED_KEY_FILE = os.environ.get("SHARED_KEY")

# Required for BE-Publisher Lib
MYSQL_BE_HOST = (
    os.environ["MYSQL_HOST"]
    if not os.environ.get("MYSQL_BE_HOST")
    else os.environ.get("MYSQL_BE_HOST")
)

MYSQL_BE_USER = (
    os.environ["MYSQL_USER"]
    if not os.environ.get("MYSQL_BE_USER")
    else os.environ.get("MYSQL_BE_USER")
)

MYSQL_BE_PASSWORD = (
    os.environ["MYSQL_PASSWORD"]
    if not os.environ.get("MYSQL_BE_PASSWORD")
    else os.environ.get("MYSQL_BE_PASSWORD")
)
MYSQL_BE_DATABASE = (
    os.environ["MYSQL_DATABASE"]
    if not os.environ.get("MYSQL_BE_DATABASE")
    else os.environ.get("MYSQL_BE_DATABASE")
)

# Required for storing user encryption information
MYSQL_HOST = (
    "127.0.0.1" if not os.environ.get("MYSQL_HOST") else os.environ.get("MYSQL_HOST")
)
MYSQL_USER = (
    "root" if not os.environ.get("MYSQL_USER") else os.environ.get("MYSQL_USER")
)

MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]

# Database creations
usersBEPUB = UsersEntity(
    mysql_host=MYSQL_BE_HOST,
    mysql_user=MYSQL_BE_USER,
    mysql_password=MYSQL_BE_PASSWORD,
    mysql_database=MYSQL_BE_DATABASE,
)

BEPubLib = Lib(usersBEPUB.db)

usersEntity = UsersEntity(
    mysql_host=MYSQL_HOST,
    mysql_user=MYSQL_USER,
    mysql_password=MYSQL_PASSWORD,
    mysql_database=MYSQL_DATABASE,
)

users = Users(usersEntity)

try:
    users.create_database_and_tables__()
except Exception as error:
    logging.exception(error)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def connect_to_imap():
    """Establishes a secure connection to the IMAP server."""
    try:
        logger.debug("Connecting to IMAP server...")
        imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        imap.login(IMAP_USERNAME, IMAP_PASSWORD)
        logger.info("Connection to IMAP server successful.")
        return imap
    except Exception as error:
        logger.error("Failed to connect to IMAP server:")
        raise error


def process_single_email(imap, email_id):
    try:
        _, data = imap.fetch(email_id, "(RFC822)")
        raw_email = data[0][1]
        email_message = email.message_from_bytes(raw_email)
        content = extract_email_content(email_message)

        processed_data = process_data(content["body"], BEPubLib, users)

        logger.debug("Encrypted data: %s", processed_data)

        if not publisher.not_active_connection(rmq_connection):
            rmq_connection, rmq_channel = publisher.init_rmq_connections()

        publisher.publish(channel=rmq_channel, data=processed_data)

        logger.info("Successfully queued email %s", email_id)

    except Exception as error:
        logger.error(f"Error processing email {email_id}:", exc_info=True)
        imap.store(email_id, "-FLAGS", "(\Seen)")


def process_unread_emails(imap):
    """Fetches and processes unread emails."""
    try:
        imap.select(MAIL_FOLDER)
        logger.debug("Searching for unread emails...")
        _, data = imap.search(None, '(UNSEEN SUBJECT "GATEWAY")')

        # TODO
        # with ThreadPoolExecutor(max_workers=5) as executor:
        #     for email_id in data[0].split():
        #         executor.submit(process_single_email, imap, email_id)

        for email_id in data[0].split():
            process_single_email(imap, email_id)

    except Exception as error:
        logger.error("Error fetching emails:")
        raise error


def extract_email_content(email_message):
    """Extracts content from the email message."""
    subject = email_message["Subject"]
    sender = email_message["From"]
    date = email_message["Date"]
    body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode()
    else:
        body = email_message.get_payload(decode=True).decode()

    content = {"subject": subject, "sender": sender, "date": date, "body": body}
    return content


def logout_from_imap(imap):
    """Logs out from the IMAP server if the connection is still valid."""
    try:
        if imap.state != "LOGOUT":
            if imap.state == "SELECTED":
                imap.close()
            imap.logout()
            logger.info("Logged out from IMAP server.")
        else:
            logger.info("IMAP connection already in logout state.")
    except Exception as error:
        logger.error("Failed to log out from IMAP server:", exc_info=True)


def main():
    """Main function to run the IMAP listener."""
    imap = connect_to_imap()
    logger.info("IMAP listener started...")

    try:
        while True:
            try:
                process_unread_emails(imap)
                logger.info("Waiting for new emails...")
            except Exception as error:
                logger.error("An unexpected error occurred:", exc_info=True)

            time.sleep(20)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt: Gracefully shutting down...")

    except Exception as error:
        logger.error("An unexpected error occurred in the main loop:", exc_info=True)

    finally:
        logout_from_imap(imap)


if __name__ == "__main__":
    main()
