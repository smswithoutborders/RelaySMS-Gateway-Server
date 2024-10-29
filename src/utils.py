"""Utility module"""

import os
import logging
from functools import wraps
from urllib.parse import urlparse, urljoin

import mysql.connector

logger = logging.getLogger(__name__)

# pylint: disable=W0212


def ensure_database_exists(host, user, password, database_name):
    """
    Decorator that ensures a MySQL database exists before executing a function.

    Args:
        host (str): The host address of the MySQL server.
        user (str): The username for connecting to the MySQL server.
        password (str): The password for connecting to the MySQL server.
        database_name (str): The name of the database to ensure existence.

    Returns:
        function: Decorated function.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                with mysql.connector.connect(
                    host=host,
                    user=user,
                    password=password,
                    charset="utf8mb4",
                    collation="utf8mb4_unicode_ci",
                ) as connection:
                    with connection.cursor() as cursor:
                        sql = "CREATE DATABASE IF NOT EXISTS " + database_name
                        cursor.execute(sql)

                logger.info(
                    "Database %s created successfully (if it didn't exist)",
                    database_name,
                )

            except mysql.connector.Error as error:
                logger.error("Failed to create database: %s", error)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def create_tables(models, db):
    """
    Creates tables for the given models if they don't exist in the specified database.

    Args:
        models: A list of Peewee Model instances.
        db: The database instance to create the tables in.
    """
    models_to_create = [
        model for model in models if not db.table_exists(model._meta.table_name)
    ]
    if models_to_create:
        db.create_tables(models_to_create)


def build_link_header(base_url, page, per_page, total_records):
    """Builds a Link header for pagination.

    Args:
        base_url (str): The base URL of the resource.
        page (int): The current page number.
        per_page (int): The number of records per page.
        total_records (int): The total number of records matching the query.

    Returns:
        str: A string representing the Link header with pagination links.
    """
    last_page = max(1, (total_records - 1) // per_page + 1)
    url_components = urlparse(base_url)
    base_url = (
        url_components.scheme + "://" + url_components.netloc + url_components.path
    )
    links = []

    if page > 1:
        links.append(
            f'<{urljoin(base_url, f"?page=1&per_page={per_page}")}>; rel="first"'
        )
        links.append(
            f'<{urljoin(base_url, f"?page={page - 1}&per_page={per_page}")}>; rel="prev"'
        )

    links.append(
        f'<{urljoin(base_url, f"?page={page}&per_page={per_page}")}>; rel="self"'
    )

    if page < last_page:
        links.append(
            f'<{urljoin(base_url, f"?page={last_page}&per_page={per_page}")}>; rel="last"'
        )
        links.append(
            f'<{urljoin(base_url, f"?page={page + 1}&per_page={per_page}")}>; rel="next"'
        )

    return ", ".join(links)


def get_configs(config_name, strict=False, default_value=None):
    """
    Retrieves the value of a configuration from the environment variables.

    Args:
        config_name (str): The name of the configuration to retrieve.
        strict (bool): If True, raises an error if the configuration
            is not found. Default is False.
        default_value (str): The default value to return if the configuration
            is not found and strict is False. Default is None.

    Returns:
        str: The value of the configuration, or default_value if not found and s
            trict is False.

    Raises:
        KeyError: If the configuration is not found and strict is True.
        ValueError: If the configuration value is empty and strict is True.
    """
    try:
        value = (
            os.environ[config_name]
            if strict
            else os.environ.get(config_name) or default_value
        )
        if strict and (value is None or value.strip() == ""):
            raise ValueError(f"Configuration '{config_name}' is missing or empty.")
        return value
    except KeyError as error:
        logger.error(
            "Configuration '%s' not found in environment variables: %s",
            config_name,
            error,
        )
        raise
    except ValueError as error:
        logger.error("Configuration '%s' is empty: %s", config_name, error)
        raise
