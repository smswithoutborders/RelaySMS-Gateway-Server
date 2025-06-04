"""Reliability Tests Controllers"""

import logging
import datetime

from playhouse.shortcuts import model_to_dict
from peewee import DoesNotExist, fn, Case

from src.models import ReliabilityTests
from src import gateway_clients

logger = logging.getLogger(__name__)

# pylint: disable=W0718,E1101,W0212

database = ReliabilityTests._meta.database


class PreCommitError(Exception):
    """Custom exception for pre-commit function failures."""


def get_all(
    filters: dict = None,
    page: int = None,
    per_page: int = None,
    order_desc: bool = True,
) -> dict:
    """Get all reliability tests according to filters and pagination."""
    results = []
    conditions = []

    if filters:
        for key, value in filters.items():
            if value is not None and key in ReliabilityTests._meta.fields:
                conditions.append(getattr(ReliabilityTests, key) == value)

    with database.atomic():
        query = ReliabilityTests.select()
        if conditions:
            query = query.where(*conditions)
        query = query.order_by(
            ReliabilityTests.id.desc() if order_desc else ReliabilityTests.id.asc()
        )

        if page and per_page:
            query = query.paginate(page, per_page)

        for test in query.dicts():
            cleaned = {
                field: (
                    int(value.timestamp())
                    if isinstance(value, datetime.datetime)
                    else value
                )
                for field, value in test.items()
            }
            results.append(cleaned)

        success_condition = (
            (ReliabilityTests.status == "success")
            & (~ReliabilityTests.sms_routed_time.is_null())
            & (
                (
                    ReliabilityTests.sms_routed_time.to_timestamp()
                    - ReliabilityTests.sms_received_time.to_timestamp()
                )
                <= 300
            )
        )

        agg_query = ReliabilityTests.select(
            fn.COUNT(ReliabilityTests.id).alias("total_records"),
            fn.SUM(Case(None, ((success_condition, 1),), 0)).alias("total_success"),
            fn.SUM(Case(None, ((ReliabilityTests.status == "timedout", 1),), 0)).alias(
                "total_failed"
            ),
        )

        if conditions:
            agg_query = agg_query.where(*conditions)

        agg_result = agg_query.dicts().get()

    return {
        "data": results,
        "total_records": agg_result["total_records"],
        "total_success": agg_result["total_success"],
        "total_failed": agg_result["total_failed"],
    }


def get_tests_for_client(
    msisdn: str,
    filters: dict = None,
    page: int = None,
    per_page: int = None,
) -> tuple:
    """Get reliability tests associated with a specific gateway client.

    Args:
        msisdn (str): The MSISDN of the gateway client.
        filters (dict, optional): A dictionary containing filtering criteria.
        page (int, optional): Page number for pagination.
        per_page (int, optional): Number of records per page for pagination.

    Returns:
        tuple: A tuple containing:
            - list of dict: A list of dictionaries containing reliability test data
                for the client.
            - int: Total number of records.
            Returns (None, None) if no gateway client is found with the provided MSISDN.
    """

    if not gateway_clients.get_by_msisdn(msisdn):
        return None, None

    filters = filters or {}
    filters["msisdn"] = msisdn

    result = get_all(filters, page, per_page)

    return result["data"], result["total_records"]


def update_timed_out_tests_status(check_interval: int = 15) -> None:
    """Update the status of reliability tests that have timed out.

    This function checks the start time of each reliability test and
    compares it with the current time. It then updates the status of
    tests that have timed out to 'timedout' in bulk.

    Args:
        check_interval (int, optional): The duration in minutes after
            which a test is considered timed out.

    Note:
        This function relies on a ReliabilityTests table in the database
            with columns 'start_time' and 'status'. The 'status' column
            should represent the status of the test, with 'success'
            indicating successful completion and 'timedout' indicating
            that the test has timed out.

    """
    threshold_time = datetime.datetime.now() - datetime.timedelta(
        minutes=check_interval
    )

    with database.atomic():
        timed_out_tests = ReliabilityTests.update(status="timedout").where(
            (ReliabilityTests.status.not_in(["success", "timedout"]))
            & (ReliabilityTests.start_time <= threshold_time)
        )
        updated_count = timed_out_tests.execute()
        logger.info("Updated %d tests to 'timedout' status.", updated_count)


def create_test_for_client(
    msisdn: str, status: str, pre_commit_funcs: list = None
) -> dict:
    """Create a reliability test for a specific gateway client.

    Args:
        msisdn (str): The MSISDN of the client.
        status (str): The test status.
        pre_commit_funcs (list, optional): A list of tuples where each tuple
            contains a function and its arguments to execute before committing
            the transaction.

    Returns:
        dict: A dictionary with test data. Returns None if the same test
              already exists.

    Example:
        # Define pre-commit functions
        def example_pre_commit_func(test_data, arg1, arg2):
            logger.info("Using test data: %s", test_data)

            # Example of rolling back transaction based on a condition
            if some_condition:
                return None

            # Otherwise, proceed with the transaction
            logger.info("Pre-commit executed with args: %s, %s", arg1, arg2)

        def another_pre_commit_func(prev_return, arg3):
            logger.info("Using previous return value: %s", prev_return)

            # Example of additional operations before committing
            logger.info("Another pre-commit executed with arg: %s", arg3)

        # Define arguments for pre-commit functions
        arg1 = "value1"
        arg2 = "value2"
        arg3 = "value3"

        # Define pre-commit functions with arguments
        pre_commit_funcs = [
            (example_pre_commit_func, (arg1, arg2)),
            (another_pre_commit_func, (arg3,))
        ]

        # Call create_test_for_client with pre-commit functions
        create_test_for_client("1234567890", "running", pre_commit_funcs)
    """
    existing_test, _ = get_tests_for_client(msisdn, filters={"status": status})

    if existing_test:
        logger.error(
            "Test not created for MSISDN: %s with status: %s, as it already exists",
            msisdn,
            status,
        )
        return None

    with database.atomic() as transaction:
        try:
            new_test = ReliabilityTests.create(msisdn=msisdn, status=status)
            new_test_data = model_to_dict(new_test, False)
            if pre_commit_funcs:
                prev_return = new_test_data
                for func, args in pre_commit_funcs:
                    args = (prev_return,) + args
                    prev_return = func(*args)

                    if prev_return is None:
                        raise PreCommitError(
                            f"Pre-commit function '{func.__name__}' failed"
                        )

            logger.info("Test created for MSISDN: %s with status: %s", msisdn, status)
            return new_test_data

        except PreCommitError as e:
            transaction.rollback()
            logger.error(str(e))
            return None

        except Exception:
            transaction.rollback()
            logger.error(
                "Failed to create test for MSISDN: %s with status: %s",
                msisdn,
                status,
                exc_info=True,
            )
            return None


def update_test_for_client(test_id: int, fields: dict, criteria: dict = None) -> int:
    """
    Update a reliability test with specified fields based on given criteria.

    Args:
        test_id (int): The ID of the test to be updated.
        fields (dict): A dictionary containing the fields and their new
            values to update.
        criteria (dict, optional): A dictionary containing filtering criteria
            to identify the test to update. Defaults to None.

    Returns:
        int: The number of rows updated in the database.
    """
    try:
        with database.atomic():
            query = ReliabilityTests.update(**fields).where(
                ReliabilityTests.id == test_id
            )

            criteria = criteria or {}

            if "id" in criteria:
                del criteria["id"]

            for key, value in criteria.items():
                if value == "is_null":
                    query = query.where(getattr(ReliabilityTests, key).is_null())
                else:
                    query = query.where(getattr(ReliabilityTests, key) == value)

            updated_count = query.execute()
            logger.info("Updated %d rows for test with ID '%d'", updated_count, test_id)
            return updated_count
    except DoesNotExist:
        logger.error("Test with ID '%d' does not exist.", test_id)
        return 0


def calculate_reliability_score_for_client(msisdn: str) -> float:
    """
    Calculate the reliability score for a gateway client based on successful SMS routing.

    Args:
        msisdn (str): The MSISDN of the client.

    Returns:
        float: Reliability percentage rounded to two decimal places.

    Notes:
        This function calculates the reliability score for a given client based on the
        percentage of successful SMS routings within a 3-minute window. Reliability is
        defined as the ratio of successful SMS routings to the total number of tests
        conducted for the client.

        A successful SMS routing is defined as a routing with a 'success' status, where
        the SMS is routed within 180 seconds (3 minutes) of being received by the system.
    """
    total_tests = (
        ReliabilityTests.select().where(ReliabilityTests.msisdn == msisdn).count()
    )

    if total_tests == 0:
        return round(0.0, 2)

    successful_tests = (
        ReliabilityTests.select()
        .where(
            ReliabilityTests.msisdn == msisdn,
            ReliabilityTests.status == "success",
            (~ReliabilityTests.sms_routed_time.is_null()),
            (
                (
                    ReliabilityTests.sms_routed_time.to_timestamp()
                    - ReliabilityTests.sms_received_time.to_timestamp()
                )
                <= 180
            ),
        )
        .count()
    )

    reliability = (successful_tests / total_tests) * 100

    return round(reliability, 2)
