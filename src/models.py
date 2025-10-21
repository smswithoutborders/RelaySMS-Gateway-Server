"""
This program is free software: you can redistribute it under the terms
of the GNU General Public License, v. 3.0. If a copy of the GNU General
Public License was not distributed with this file, see <https://www.gnu.org/licenses/>.
"""

import datetime
from peewee import (
    Model,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKeyField,
    BlobField,
    IntegerField,
)
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


class MessageSegments(Model):
    """Model representing cached message segments."""

    session_id = CharField()
    sender_id = CharField()
    segment_number = IntegerField()
    total_segments = IntegerField()
    image_length = IntegerField(default=0)
    text_length = IntegerField(default=0)
    content = BlobField()
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        """Meta class to define database connection."""

        database = database
        table_name = "message_segments"
        indexes = (
            (("session_id", "sender_id", "segment_number"), True),
            (("created_at",), False),
        )


database.create_tables([GatewayClients, ReliabilityTests, MessageSegments], safe=True)
