"""API V2 Blueprint"""

import logging

from flask import Blueprint, request, jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound

from src.db import connect
from src.payload_service import decode_and_publish

v2_blueprint = Blueprint("v2", __name__)
CORS(v2_blueprint)

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


@v2_blueprint.before_request
def _db_connect():
    """Connect to the database before processing the request."""
    database.connect(reuse_if_open=True)


@v2_blueprint.teardown_request
def _db_close(response):
    """Close the database connection after processing the request."""
    database.close()
    return response


@v2_blueprint.after_request
def after_request(response):
    """Set security headers after each request."""
    response = set_security_headers(response)
    return response


@v2_blueprint.route("/sms/platform/<string:platform>", methods=["POST"])
def publish_relaysms_payload(platform):
    """Publishes RelaySMS Payload."""

    request_data = request.json
    publisher_response, err = decode_and_publish(request_data)

    if err:
        raise BadRequest(err)

    return jsonify({"publisher_response": publisher_response})


@v2_blueprint.errorhandler(BadRequest)
@v2_blueprint.errorhandler(NotFound)
def handle_bad_request_error(error):
    """Handle BadRequest errors."""
    logger.error(error.description)
    return jsonify({"error": error.description}), error.code


@v2_blueprint.errorhandler(Exception)
def handle_generic_error(error):
    """Handle generic errors."""
    logger.exception(error)
    return (
        jsonify({"error": "Oops! Something went wrong. Please try again later."}),
        500,
    )
