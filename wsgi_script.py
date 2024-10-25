"""WSGI script for running the application."""

from src.main import app as application


class LoggingMiddleware:
    """Middleware class for logging incoming requests and outgoing responses."""

    def __init__(self, app_handler):
        """Initialize the LoggingMiddleware."""
        self.__application = app_handler

    def __call__(self, environ, start_response):
        """Call method to handle the request."""
        request_method = environ["REQUEST_METHOD"]
        path_info = environ["PATH_INFO"]
        query_string = environ.get("QUERY_STRING", "")

        if query_string:
            path_info += f"?{query_string}"

        def _start_response(status, headers, *args):
            """
            Custom start_response function to log response status.
            """
            server_protocol = environ.get("SERVER_PROTOCOL", "-")
            log_msg = f'"{request_method} {path_info} {server_protocol}" {status} -'
            print(log_msg)
            return start_response(status, headers, *args)

        return self.__application(environ, _start_response)


application = LoggingMiddleware(application)
