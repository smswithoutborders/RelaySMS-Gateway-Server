"""Database Models."""

from datetime import datetime
from peewee import CharField, DateTimeField, ForeignKeyField, DecimalField

from src.db import connect
from src.utils import create_tables

database = connect()


class GatewayClients(database.Model):
    """Model representing Gateway Clients."""

    msisdn = CharField(primary_key=True)
    country = CharField()
    operator = CharField()
    operator_code = CharField()
    protocols = CharField()
    reliability = DecimalField(max_digits=5, decimal_places=2, default=0.00)
    last_published_date = DateTimeField(default=datetime.now)

    # pylint: disable=R0903
    class Meta:
        """Meta class to define database connection."""

        database = database
        table_name = "gateway_clients"


class ReliabilityTests(database.Model):
    """Model representing Gateway Clients Reliability Tests."""

    start_time = DateTimeField(default=datetime.now)
    sms_sent_time = DateTimeField(null=True)
    sms_received_time = DateTimeField(null=True)
    sms_routed_time = DateTimeField(null=True)
    status = CharField(default="pending")
    msisdn = CharField()
    reliability_score = DecimalField(max_digits=5, decimal_places=2, null=True)

    # pylint: disable=R0903
    class Meta:
        """Meta class to define database connection."""

        database = database
        table_name = "reliability_tests"


create_tables([GatewayClients, ReliabilityTests])
