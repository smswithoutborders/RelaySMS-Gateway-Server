import logging

from src.users_entity import UsersEntity

import mysql.connector
from mysql.connector import errorcode

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class User:

    id = None
    public_key = None
    msisdn_hash = None
    shared_key = None
    mgf1ParameterSpec = None
    hashingAlgorithm = None


class Users(User):
    TABLES = {}

    TABLE_NAME = "gateway_server_users"

    TABLES[TABLE_NAME] = (
        f"CREATE TABLE `{TABLE_NAME}` ("
        "  `msisdn_hash` varchar(256) NOT NULL,"
        "  `shared_key` text NOT NULL,"
        "  `public_key` text NOT NULL,"
        "  `mgf1ParameterSpec` text NOT NULL,"
        "  `hashingAlgorithm` text NOT NULL,"
        "  `date` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
        "  PRIMARY KEY (`msisdn_hash`)"
        ") ENGINE=InnoDB"
    )

    def __init__(self, userEntity: UsersEntity) -> None:
        """Creates new user record if not exist.

        This method would create a record for the user and store in the path of
        user_record_filepath.

        Args: session_id (str): The last session ID being tracked for this session.
            public_key (str): User's public key.
            shared_key (str): Shared key for encrypting and decrypting incoming messages.
        """

        self.userEntity = userEntity
        self.__connect__()

    def __connect__(self):
        """ """
        self.connection = mysql.connector.connect(
            host=self.userEntity.MYSQL_HOST,
            user=self.userEntity.MYSQL_USER,
            database=self.userEntity.MYSQL_DATABASE,
            password=self.userEntity.MYSQL_PASSWORD,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
        )

        self.connection.autocommit = True

    def __get_cursor__(self, buffered=None, dictionary=None):
        """ """
        if not self.connection.is_connected():
            self.__connect__()

        return self.connection.cursor(buffered=buffered, dictionary=dictionary)

    def __create_database__(self):
        """ """
        cursor = self.__get_cursor__()
        try:
            cursor.execute(
                f"CREATE DATABASE {self.userEntity.MYSQL_DATABASE} "
                "DEFAULT CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'"
            )
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DB_CREATE_EXISTS:
                logger.warning(
                    "Database [%s] creation: already exist",
                    self.userEntity.MYSQL_DATABASE,
                )
            else:
                raise err

    def __create_tables__(self):
        """ """
        cursor = self.__get_cursor__()

        for table_name, table_description in self.TABLES.items():
            try:
                cursor.execute(table_description)
            except (mysql.connector.Error, Exception) as err:
                if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                    logger.warning(
                        "User table[%s] populate: already exist.", table_name
                    )
                else:
                    raise err
            else:
                logger.info("User table[%s] populate: OK.", table_name)

        cursor.close()

    def create_database_and_tables__(self) -> None:
        """ """
        try:
            self.__create_database__()
        except Exception as error:
            raise error

        try:
            self.__create_tables__()
        except Exception as error:
            raise error

    def store_shared_key(self, shared_key: str) -> None:
        """
        TODO: shared key should be encrypted when stored
        """

    def commit(self, user: User) -> None:
        """
        insert or update
        """
        cursor = self.__get_cursor__()

        insert_query = (
            f"INSERT INTO {self.TABLE_NAME} "
            "(public_key, shared_key, msisdn_hash, mgf1ParameterSpec, hashingAlgorithm) "
            "VALUES (%s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE "
            "public_key = VALUES(public_key), "
            "shared_key = VALUES(shared_key), "
            "mgf1ParameterSpec = VALUES(mgf1ParameterSpec), "
            "hashingAlgorithm = VALUES(hashingAlgorithm)"
        )

        try:
            cursor.execute(
                insert_query,
                (
                    user.public_key,
                    user.shared_key,
                    user.msisdn_hash,
                    user.mgf1ParameterSpec,
                    user.hashingAlgorithm,
                ),
            )

            self.connection.commit()

        except Exception as error:
            raise error

        finally:
            cursor.close()

    def delete(self, user: User) -> None:
        """
        delete
        """
        cursor = self.__get_cursor__()

        delete_query = f"DELETE FROM {self.TABLE_NAME} " "WHERE msisdn_hash = %s"

        try:
            cursor.execute(delete_query, (user.msisdn_hash,))

            self.connection.commit()

        except Exception as error:
            raise error

        finally:
            cursor.close()

    def find(self, msisdn_hash: str):
        """ """
        if not msisdn_hash:
            return User()

        cursor = self.__get_cursor__(buffered=True, dictionary=True)
        query = (
            "SELECT public_key, shared_key, msisdn_hash, mgf1ParameterSpec, hashingAlgorithm "
            f"FROM {self.TABLE_NAME} WHERE msisdn_hash = %s"
        )
        try:
            cursor.execute(query, (msisdn_hash,))
        except Exception as error:
            raise error
        else:
            user = User()
            for row in cursor:
                user.public_key = row["public_key"]
                user.shared_key = row["shared_key"]
                user.msisdn_hash = row["msisdn_hash"]
                user.mgf1ParameterSpec = row["mgf1ParameterSpec"]
                user.hashingAlgorithm = row["hashingAlgorithm"]

                cursor.close()

            return user
        finally:
            cursor.close()
