import pytest

from pipeline.connect import get_connection

pytestmark = pytest.mark.snowflake


@pytest.fixture(scope="module")
def cur():
    with get_connection() as conn:
        yield conn.cursor()


def test_logged_in_as_pipeline_user(cur):
    user, role = cur.execute("select current_user(), current_role()").fetchone()
    assert (user, role) == ("PIPELINE_SVC", "PIPELINE_ROLE")


def test_organizer_stage_lists_data(cur):
    rows = cur.execute("list @LATAM_BANK.RAW.ORGANIZER_STAGE pattern='.*customers.*'").fetchall()
    assert rows, "organizer stage reachable and customers file present"


def test_serving_stage_reachable(cur):
    cur.execute("list @LATAM_BANK.RAW.SERVING_STAGE")  # empty is fine; an auth error raises
