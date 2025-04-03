"""API V3 Blueprint"""

import logging
import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound

from src import gateway_clients, reliability_tests
from src.db import connect
from src.utils import build_link_header
from src.payload_service import decode_and_publish
from src.models import ReliabilityTests, GatewayClients

v3_blueprint = Blueprint("v3", __name__, url_prefix="/v3")
CORS(v3_blueprint, expose_headers=["X-Total-Count", "X-Page", "X-Per-Page", "Link"])

database = connect()

logger = logging.getLogger(__name__)


def set_security_headers(response):
    """Set security headers for each response."""
    security_headers = {
        "Strict-Transport-Security": "max-age=63072000; includeSubdomains",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "script-src 'self'; object-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Cache-Control": "no-cache",
        "Permissions-Policy": (
            "accelerometer=(), ambient-light-sensor=(), autoplay=(), battery=(), camera=(), "
            "clipboard-read=(), clipboard-write=(), cross-origin-isolated=(), display-capture=(), "
            "document-domain=(), encrypted-media=(), execution-while-not-rendered=(), "
            "execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), "
            "gyroscope=(), magnetometer=(), microphone=(), midi=(), navigation-override=(), "
            "payment=(), picture-in-picture=(), publickey-credentials-get=(), screen-wake-lock=(), "
            "speaker=(), speaker-selection=(), sync-xhr=(), usb=(), web-share=(), "
            "xr-spatial-tracking=()"
        ),
    }

    for header, value in security_headers.items():
        response.headers[header] = value

    return response


@v3_blueprint.before_request
def _db_connect():
    """Connect to the database before processing the request."""
    database.connect(reuse_if_open=True)


@v3_blueprint.teardown_request
def _db_close(response):
    """Close the database connection after processing the request."""
    database.close()
    return response


@v3_blueprint.after_request
def after_request(response):
    """Set security headers after each request."""
    response = set_security_headers(response)
    return response


@v3_blueprint.route("/clients", methods=["GET"])
def get_gateway_clients():
    """Get gateway clients with optional filters"""

    filters = {
        "country": request.args.get("country") or None,
        "operator": request.args.get("operator") or None,
        "protocols": request.args.get("protocols") or None,
        "last_published_date": request.args.get("last_published_date") or None,
    }

    try:
        page = int(request.args.get("page") or 1)
        per_page = int(request.args.get("per_page") or 10)

        if page < 1 or per_page < 1:
            raise ValueError
    except ValueError as exc:
        raise BadRequest(
            "Invalid page or per_page parameter. Must be positive integers."
        ) from exc

    last_published_date_str = filters.get("last_published_date")
    if last_published_date_str:
        try:
            filters["last_published_date"] = datetime.fromisoformat(
                last_published_date_str
            )
        except ValueError as exc:
            raise BadRequest(
                "Invalid last_published_date. "
                "Please provide a valid ISO format datetime (YYYY-MM-DD)."
            ) from exc

    results, total_records = gateway_clients.get_all(filters, page, per_page)

    response = jsonify(results)
    response.headers["X-Total-Count"] = str(total_records)
    response.headers["X-Page"] = str(page)
    response.headers["X-Per-Page"] = str(per_page)

    link_header = build_link_header(request.base_url, page, per_page, total_records)
    if link_header:
        response.headers["Link"] = link_header

    return response


@v3_blueprint.route("/clients/<string:msisdn>/tests", methods=["GET"])
def get_gateway_client_tests(msisdn):
    """Get reliability tests for a specific gateway client with optional filters."""

    try:
        page = int(request.args.get("page") or 1)
        per_page = int(request.args.get("per_page") or 10)

        if page < 1 or per_page < 1:
            raise ValueError
    except ValueError as exc:
        raise BadRequest(
            "Invalid page or per_page parameter. Must be positive integers."
        ) from exc

    reliability_tests.update_timed_out_tests_status()
    client_tests, total_records = reliability_tests.get_tests_for_client(
        msisdn, page=int(page), per_page=int(per_page)
    )

    if client_tests is None:
        raise NotFound(f"No gateway client found with MSISDN: {msisdn}")

    response = jsonify(client_tests)
    response.headers["X-Total-Count"] = str(total_records)
    response.headers["X-Page"] = str(page)
    response.headers["X-Per-Page"] = str(per_page)

    link_header = build_link_header(request.base_url, page, per_page, total_records)
    if link_header:
        response.headers["Link"] = link_header

    return response


@v3_blueprint.route("/clients/countries", methods=["GET"])
def get_all_countries():
    """Get all countries for clients."""
    countries = gateway_clients.get_all_countries()
    return jsonify(countries)


@v3_blueprint.route("/clients/<string:country>/operators", methods=["GET"])
def get_operators_for_country(country):
    """Get all operators for a specific country."""
    if not country:
        raise BadRequest("Country parameter is required.")

    operators = gateway_clients.get_operators_for_country(country.lower())
    return jsonify(operators)


@v3_blueprint.route("/publish", methods=["POST"])
def publish_relaysms_payload():
    """Publishes RelaySMS Payload."""

    request_data = request.json
    publisher_response, err = decode_and_publish(request_data, "http")

    if err:
        raise BadRequest(err)

    return jsonify({"publisher_response": publisher_response})


@v3_blueprint.route("/clients/tests", methods=["POST"])
def start_reliability_test():
    """Start a reliability test for a gateway client."""

    request_data = request.json

    msisdn = request_data.get("msisdn")
    test_start_time = request_data.get("test_start_time")

    if not msisdn or not test_start_time:
        raise BadRequest("Both 'msisdn' and 'test_start_time' are required.")

    try:
        test_start_time = datetime.fromisoformat(test_start_time)
    except ValueError:
        raise BadRequest(
            "Invalid 'test_start_time' format. Use ISO format (YYYY-MM-DDTHH:MM:SS)."
        )
    
    try:
        new_test = ReliabilityTests.create(
            msisdn=msisdn,
            start_time=test_start_time,
            status="pending",
            sms_sent_time=None,
            sms_received_time=None,
            sms_routed_time=None,
        )
    except Exception as exc:
        logger.exception("Failed to save reliability test to the database.")
        raise BadRequest("Failed to start the reliability test.") from exc

    return jsonify({"message": "Test started successfully", "test_id": str(new_test.id)})


@v3_blueprint.errorhandler(BadRequest)
@v3_blueprint.errorhandler(NotFound)
def handle_bad_request_error(error):
    """Handle BadRequest errors."""
    logger.error(error.description)
    return jsonify({"error": error.description}), error.code


@v3_blueprint.errorhandler(Exception)
def handle_generic_error(error):
    """Handle generic errors."""
    logger.exception(error)
    return (
        jsonify({"error": "Oops! Something went wrong. Please try again later."}),
        500,
    )
