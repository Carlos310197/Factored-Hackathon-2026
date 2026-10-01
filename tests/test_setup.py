import pytest
from pipeline.setup import render, split_statements

def test_render_substitutes_tokens():
    assert render("URL='s3://${BUCKET}/data/'", {"BUCKET": "b1"}) == "URL='s3://b1/data/'"

def test_render_missing_token_raises():
    with pytest.raises(KeyError):
        render("${MISSING}", {})

def test_split_statements_ignores_comments_and_blank():
    sql = "-- c\ncreate warehouse w;\n\nuse role x;\n"
    assert split_statements(sql) == ["create warehouse w", "use role x"]
