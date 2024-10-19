"""
A module for handling application logging.

This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import os
import logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, LOG_LEVEL, None)

if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log level: {LOG_LEVEL}")

logging.basicConfig(
    level=numeric_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def get_logger(name: str = None) -> logging.Logger:
    """Retrieves a logger instance configured with the specified name.

    Args:
        name (str, optional): The name of the logger. If None, the root logger is
            returned.

    Returns:
        logging.logger: A configured logger instance.
    """
    return logging.getLogger(name)
