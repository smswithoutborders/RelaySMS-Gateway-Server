"""
This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import datetime
from peewee import Model, CharField, DateTimeField, DecimalField, ForeignKeyField
from src.db import connect

database = connect()


class GatewayClients(Model):
    """Model representing Gateway Clients."""

    msisdn = CharField(primary_key=True)
    country = CharField()
    operator = CharField()
    operator_code = CharField()
    protocols = CharField()
    reliability = DecimalField(max_digits=5, decimal_places=2, default=0.00)
    last_published_date = DateTimeField(default=datetime.datetime.now)

    class Meta:
        """Meta class to define database connection."""

        database = database
        table_name = "gateway_clients"


class ReliabilityTests(Model):
    """Model representing Gateway Clients Reliability Tests."""

    start_time = DateTimeField(default=datetime.datetime.now)
    sms_sent_time = DateTimeField(null=True)
    sms_received_time = DateTimeField(null=True)
    sms_routed_time = DateTimeField(null=True)
    status = CharField(default="pending")
    msisdn = ForeignKeyField(
        GatewayClients, column_name="msisdn", backref="reliability_tests"
    )

    class Meta:
        """Meta class to define database connection."""

        database = database
        table_name = "reliability_tests"


database.create_tables([GatewayClients, ReliabilityTests], safe=True)
