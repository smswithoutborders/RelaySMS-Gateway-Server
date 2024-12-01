"""Gateway Clients Controllers"""

import logging
import datetime

from peewee import fn, DoesNotExist

from src.models import GatewayClients

logger = logging.getLogger(__name__)


database = GatewayClients._meta.database


def get_all(filters=None, page=None, per_page=None) -> tuple:
    """Get all gateway clients according to the filters, pagination.

    Args:
        filters (dict, optional): A dictionary containing filtering criteria.
        page (int, optional): Page number for pagination.
        per_page (int, optional): Number of records per page for pagination.

    Returns:
        tuple: A tuple containing a list of dictionaries containing client data and total_records.
    """
    results = []
    query = GatewayClients.select().dicts()

    if filters:
        conditions = []
        for key, value in filters.items():
            if value is not None:
                if key == "country":
                    conditions.append(
                        fn.lower(getattr(GatewayClients, key)) == value.lower()
                    )
                elif key in ("protocols", "operator"):
                    conditions.append(
                        fn.lower(getattr(GatewayClients, key)).contains(value.lower())
                    )
                elif key == "last_published_date":
                    conditions.append(
                        getattr(GatewayClients, key).truncate("day") == value
                    )
                else:
                    conditions.append(getattr(GatewayClients, key) == value)

        if conditions:
            query = query.where(*conditions).dicts()

    total_records = query.count() or 0

    if page is not None and per_page is not None:
        query = query.paginate(page, per_page)

    for client in query:
        client = {
            field: (
                int(value.timestamp())
                if isinstance(value, datetime.datetime)
                else value
            )
            for field, value in client.items()
        }

        client["protocols"] = (
            client.get("protocols", "").split(",") if client.get("protocols") else []
        )

        results.append(client)

    return results, total_records


def get_by_msisdn(msisdn: str) -> dict:
    """Retrieve a gateway client by its MSISDN.

    Args:
        msisdn (str): The MSISDN of the gateway client to retrieve.

    Returns:
        dict: A dictionary containing client data if a matching client is found,
            or None if no client with the provided MSISDN exists.
    """
    client = (
        GatewayClients.select()
        .where(GatewayClients.msisdn == msisdn)
        .dicts()
        .get_or_none()
    )

    if not client:
        return None

    client = {
        field: int(value.timestamp()) if isinstance(value, datetime.datetime) else value
        for field, value in client.items()
    }

    client["protocols"] = client.get("protocols", "").split(",")

    return client


def update_by_msisdn(msisdn: str, fields: dict) -> bool:
    """Update a gateway client by its MSISDN.

    Args:
        msisdn (str): The MSISDN of the gateway client to update.
        fields (dict): A dictionary containing the fields to update
            along with their new values.

    Returns:
        bool: True if the client is updated successfully, False otherwise.
    """
    try:
        client = GatewayClients.get(GatewayClients.msisdn == msisdn)

        with database.atomic():
            for field, value in fields.items():
                setattr(client, field, value)
            client.save()

        return True

    except DoesNotExist:
        return False


def get_all_countries() -> list:
    """Retrieve a list of all unique countries from the gateway clients.

    Returns:
        list: A list containing names of all unique countries.
    """
    countries = (
        GatewayClients.select(GatewayClients.country)
        .distinct()
        .where(GatewayClients.country.is_null(False))
        .tuples()
    )
    return [country[0] for country in countries]


def get_operators_for_country(country: str) -> list:
    """Retrieve a list of all unique operators for a specific country.

    Args:
        country (str): The name of the country for which operators are
            to be retrieved.

    Returns:
        list: A list containing names of all unique operators for the
            specified country.
    """
    operators = (
        GatewayClients.select(GatewayClients.operator)
        .distinct()
        .where(
            (GatewayClients.country == country)
            & (GatewayClients.operator.is_null(False))
        )
        .tuples()
    )
    return [operator[0] for operator in operators]
