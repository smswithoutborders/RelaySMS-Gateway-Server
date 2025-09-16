"""Module for connecting to a database."""

from peewee import Database, DatabaseError, MySQLDatabase, SqliteDatabase
from playhouse.shortcuts import ReconnectMixin
from src.utils import ensure_database_exists, get_configs
from logutils import get_logger

logger = get_logger(__name__)

DATABASE_CONFIGS = {
    "mode": get_configs("MODE", default_value="development"),
    "mysql": {
        "database": get_configs("MYSQL_DATABASE"),
        "host": get_configs("MYSQL_HOST"),
        "password": get_configs("MYSQL_PASSWORD"),
        "user": get_configs("MYSQL_USER"),
    },
    "sqlite": {
        "database_path": get_configs("SQLITE_DATABASE_PATH"),
    },
}


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    """
    A custom MySQLDatabase class with automatic reconnection capability.

    This class inherits from both ReconnectMixin and MySQLDatabase
    to provide automatic reconnection functionality in case the database
    connection is lost.
    """


def is_mysql_config_complete() -> bool:
    """
    Checks if all required MySQL configurations are present.

    Returns:
        bool: True if all MySQL configurations are complete, False otherwise.
    """
    logger.debug("Checking if MySQL configuration is complete...")
    mysql_config = DATABASE_CONFIGS["mysql"]
    required_keys = ["database", "host", "password", "user"]
    return all(mysql_config.get(key) for key in required_keys)


def connect() -> Database:
    """
    Connects to the appropriate database based on the mode.

    If the mode is 'testing', it returns None.

    If the mode is 'development', it checks if MySQL credentials
    are complete. If they are, it connects to the MySQL database,
    otherwise, it falls back to the SQLite database.

    If the mode is not 'testing' or 'development', it connects
    to the MySQL database.

    Returns:
        Database: The connected database object.
    """
    mode = DATABASE_CONFIGS["mode"]
    logger.debug("Database connection mode: %s", mode)

    if mode == "testing":
        logger.debug("Mode is 'testing'. No database connection will be made.")
        return None

    if mode == "development":
        if is_mysql_config_complete():
            return connect_to_mysql()
        logger.warning(
            "MySQL configuration is incomplete. Falling back to SQLite database."
        )
        return connect_to_sqlite()

    return connect_to_mysql()


@ensure_database_exists(
    DATABASE_CONFIGS["mysql"]["host"],
    DATABASE_CONFIGS["mysql"]["user"],
    DATABASE_CONFIGS["mysql"]["password"],
    DATABASE_CONFIGS["mysql"]["database"],
)
def connect_to_mysql() -> ReconnectMySQLDatabase:
    """
    Connects to the MySQL database.

    Returns:
        ReconnectMySQLDatabase: The connected MySQL database object with reconnection capability.

    Raises:
        DatabaseError: If failed to connect to the database.
    """
    logger.debug(
        "Attempting to connect to MySQL database '%s' at '%s'...",
        DATABASE_CONFIGS["mysql"]["database"],
        DATABASE_CONFIGS["mysql"]["host"],
    )
    try:
        db = ReconnectMySQLDatabase(
            DATABASE_CONFIGS["mysql"]["database"],
            user=DATABASE_CONFIGS["mysql"]["user"],
            password=DATABASE_CONFIGS["mysql"]["password"],
            host=DATABASE_CONFIGS["mysql"]["host"],
        )
        db.connect()
        return db
    except DatabaseError as error:
        logger.error(
            "Failed to connect to MySQL database '%s' at '%s': %s",
            DATABASE_CONFIGS["mysql"]["database"],
            DATABASE_CONFIGS["mysql"]["host"],
            error,
        )
        raise error


def connect_to_sqlite() -> SqliteDatabase:
    """
    Connects to the SQLite database.

    Returns:
        SqliteDatabase: The connected SQLite database object.

    Raises:
        DatabaseError: If failed to connect to the database.
    """
    db_path = DATABASE_CONFIGS["sqlite"]["database_path"]
    logger.debug("Attempting to connect to SQLite database at '%s'...", db_path)
    try:
        db = SqliteDatabase(db_path)
        db.connect()
        return db
    except DatabaseError as error:
        logger.error("Failed to connect to SQLite database at '%s': %s", db_path, error)
        raise error
