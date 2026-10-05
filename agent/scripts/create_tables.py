"""Create the agent's DynamoDB tables (idempotent).
Local:  DYNAMODB_ENDPOINT=http://localhost:8000 uv run python scripts/create_tables.py"""
import os

import boto3

from bankagent.store.tables import create_tables

if __name__ == "__main__":
    client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"),
                          endpoint_url=os.environ.get("DYNAMODB_ENDPOINT") or None)
    print(create_tables(client, os.environ.get("TABLE_PREFIX", "bankagent-dev")))
