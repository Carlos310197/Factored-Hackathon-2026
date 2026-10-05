import pytest

from asis.load import connect
from asis.tests.fixtures import write_fixture


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory):
    return write_fixture(tmp_path_factory.mktemp("drop") / "data")


@pytest.fixture(scope="session")
def con(data_dir):
    return connect(data_dir)
