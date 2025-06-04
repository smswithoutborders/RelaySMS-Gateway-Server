"""Reliability Tests CLI"""

import os
import logging
import json
import base64
import argparse
import requests

from src.models import ReliabilityTests
from src import aes, gateway_clients, reliability_tests

DEKU_CLOUD_URL = os.environ.get("DEKU_CLOUD_URL")
DEKU_CLOUD_PROJECT_REF = os.environ.get("DEKU_CLOUD_PROJECT_REF")
DEKU_CLOUD_SERVICE_ID = os.environ.get("DEKU_CLOUD_SERVICE_ID")
DEKU_CLOUD_ACCOUNT_SID = os.environ.get("DEKU_CLOUD_ACCOUNT_SID")
DEKU_CLOUD_AUTH_TOKEN = os.environ.get("DEKU_CLOUD_AUTH_TOKEN")

SHARED_KEY_FILE = os.environ.get("SHARED_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("[RT CLI]")

# pylint: disable=W0718,E1101,W0212


def update_gateway_client_reliability_score(_, msisdn: str):
    """
    Update reliability score for a gateway client.

    Args:
        msisdn: MSISDN of the gateway client.

    Returns:
        True if the reliability score was updated successfully, False otherwise.
    """
    reliability_score = reliability_tests.calculate_reliability_score_for_client(msisdn)

    if reliability_score == 0.0:
        logger.warning(
            "Reliability score for gateway client with MSISDN %s is %s",
            msisdn,
            reliability_score,
        )

    if not gateway_clients.update_by_msisdn(msisdn, {"reliability": reliability_score}):
        logger.error(
            "Failed to update gateway client reliability score with MSISDN: %s", msisdn
        )
        return None

    return True


def make_deku_api_call(test_data, mock=False):
    """Make an API call to Deku Cloud to send test data.

    Args:
        test_data: The test data containing 'msisdn' and 'base64 encoded ciphertext'
        mock (bool): Whether to mock the API call or not.

    Returns:
        int or None: HTTP status code of the API call or None if failed.
    """
    msisdn, payload = test_data

    if mock:
        logger.info("Mocking API call to Deku Cloud.")
        logger.info("MSISDN: %s", msisdn)
        logger.info("PAYLOAD: %s", payload)
        return 200

    if (
        not DEKU_CLOUD_URL
        or not DEKU_CLOUD_ACCOUNT_SID
        or not DEKU_CLOUD_AUTH_TOKEN
        or not DEKU_CLOUD_PROJECT_REF
        or not DEKU_CLOUD_SERVICE_ID
    ):
        logger.error("Deku Cloud environment variables are not set.")
        return None

    data = {"sid": "", "to": msisdn, "body": payload}
    auth = (DEKU_CLOUD_ACCOUNT_SID, DEKU_CLOUD_AUTH_TOKEN)
    url = f"{DEKU_CLOUD_URL}/v1/projects/{DEKU_CLOUD_PROJECT_REF}/services/{DEKU_CLOUD_SERVICE_ID}"

    try:
        response = requests.post(url, json=data, auth=auth, timeout=10)
        response.raise_for_status()
        return response.status_code
    except requests.exceptions.RequestException:
        logger.error("Failed to make API call to Deku Cloud.", exc_info=True)
        return None


def encrypt_payload(payload):
    """Encrypts test payload using AES encryption.

    Args:
        payload (bytes): The test payload to be encrypted.

    Returns:
        str or None: The base64 encoded ciphertext if successful, None otherwise.
    """
    if not SHARED_KEY_FILE:
        logger.error("SHARED_KEY_FILE environment variable not set.")
        return None

    with open(SHARED_KEY_FILE, "r", encoding="utf-8") as f:
        encryption_key = f.readline().strip()[:32]

    if not encryption_key:
        logger.error("Encryption key is empty or invalid.")
        return None

    try:
        ciphertext = aes.AESCipher.encrypt(shared_key=encryption_key, data=payload)
        return base64.b64encode(ciphertext).decode("utf-8")
    except Exception:
        logger.error("Failed to encrypt payload.", exc_info=True)
        return None


def create_test_payload(test_data):
    """Creates a test payload and encrypts it.

    Args:
        test_data (dict): Test data containing 'id' and 'msisdn'.

    Returns:
        tuple or None: Tuple containing MSISDN and base64 encoded ciphertext
            of the encrypted payload, or None if creation failed.
    """
    test_payload = {"test_id": test_data["id"], "msisdn": test_data["msisdn"]}
    test_ciphertext = encrypt_payload(payload=bytes(json.dumps(test_payload), "utf-8"))

    if not test_ciphertext:
        logger.error(
            "Failed to create test payload for MSISDN: %s",
            test_data["msisdn"],
        )
        return None

    return test_data["msisdn"], test_ciphertext


def start_tests(msisdn=None, all_tests=False, mock_api=False):
    """Start reliability tests for specified MSISDN or all MSISDNs.

    Args:
        msisdn (str, optional): MSISDN for which tests are to be started.
        all_tests (bool, optional): Flag to indicate if tests are to be
            started for all MSISDNs.
        mock_api (bool, optional): Whether to mock the API call or not.
    """
    if not msisdn and not all_tests:
        logger.error(
            "Please provide an MSISDN or use --all option to start tests for all MSISDNs."
        )
        return

    if all_tests:
        clients, _ = gateway_clients.get_all()
    else:
        clients = [gateway_clients.get_by_msisdn(msisdn=msisdn)]

    for client in clients:
        if not client:
            logger.info("No client found with MSISDN: %s", msisdn)
            continue

        pre_commit_funcs = [
            (create_test_payload, ()),
            (make_deku_api_call, (mock_api,)),
            (update_gateway_client_reliability_score, (client["msisdn"],)),
        ]

        reliability_tests.create_test_for_client(
            client["msisdn"], "running", pre_commit_funcs
        )


def view_test_data(msisdn=None):
    """View test data for specified MSISDN or all test data in the database.

    Args:
        msisdn (str, optional): MSISDN for which test data is to be viewed.
    """
    with ReliabilityTests._meta.database.atomic():
        try:
            result = reliability_tests.get_all()
            tests = result["data"]

            if msisdn:
                tests, _ = reliability_tests.get_tests_for_client(msisdn)

            if not tests:
                logger.info("No tests found.")
                return

            print(f"{'Tests':=^60}")
            for test in tests:
                print("-" * 60)
                for key, value in test.items():
                    print(f"{key.upper()}: {value}")

        except Exception:
            logger.error("Failed to get test(s).", exc_info=True)


def main():
    """Parse command line arguments and execute corresponding action."""
    parser = argparse.ArgumentParser(
        description="Gateway Clients Reliability Tests CLI"
    )

    parser.add_argument(
        "action",
        choices=["start", "view"],
        help="Action to perform: start or view tests",
    )
    parser.add_argument(
        "--msisdn", help="MSISDN for which tests are to be started or viewed"
    )
    parser.add_argument(
        "--all", action="store_true", help="Start tests for all MSISDNs"
    )

    parser.add_argument("--mock-api", action="store_true", help="Mock the API call")

    args = parser.parse_args()

    reliability_tests.update_timed_out_tests_status()

    if args.action == "start":
        start_tests(args.msisdn, args.all, args.mock_api)
    elif args.action == "view":
        view_test_data(args.msisdn)


if __name__ == "__main__":
    main()
