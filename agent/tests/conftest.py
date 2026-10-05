import os

import pytest

# moto and boto3 need credentials and a region even when mocked.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture(scope="session")
def serving_root(tmp_path_factory):
    from tests.fixtures.serving_fixture import build_serving
    return build_serving(tmp_path_factory.mktemp("serving"))


@pytest.fixture(scope="session")
def history_serving(tmp_path_factory):
    from tests.fixtures.resolver_serving import build_history_serving
    return build_history_serving(tmp_path_factory.mktemp("history_serving"))
  
@pytest.fixture
def ddb_store():
    import boto3
    from moto import mock_aws

    from bankagent.store.repos import Store
    from bankagent.store.tables import create_tables

    with mock_aws():
        create_tables(boto3.client("dynamodb", region_name="us-east-2"), "t")
        yield Store.connect("t", "us-east-2")
