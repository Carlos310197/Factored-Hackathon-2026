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
