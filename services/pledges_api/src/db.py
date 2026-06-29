"""Shared DynamoDB access for the pledges API.

One place resolves the pledges table, so routes don't each re-create a boto3
resource the way the old per-endpoint handlers did (decision D19 — shared modules,
no per-file duplication). The resource is created lazily per call, so the table is
resolved inside whatever AWS (or moto, in tests) context is active when a request
is handled.
"""
import os

import boto3

_dynamodb = None


def get_table():
    """Return the pledges DynamoDB table (name from ``PLEDGES_TABLE_NAME``).

    The boto3 resource is created once and cached so warm Lambda invocations reuse
    the same connection pool; only the (cheap) table lookup runs per call. It is
    created lazily — on the first request — so it lands inside whatever AWS (or
    moto, in tests) context is active rather than at import time.
    """
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(os.environ["PLEDGES_TABLE_NAME"])
