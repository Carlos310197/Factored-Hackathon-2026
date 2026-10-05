import json

import boto3
import pytest
import yaml
from moto import mock_aws

import bankagent.identity.lambda_handler as lh
from bankagent.auth.tokens import generate_keypair
from bankagent.identity.users import hash_password

USERS_YAML = "# LABELED TEST identities (fixture)\n" + yaml.safe_dump({"users": [
    {"username": "demo01", "password_sha256": hash_password("x"), "otp": "123456",
     "customer_id": "CLI-FIXA00000001", "lang": "es"}]})
ENV = {"IDP_ISSUER": "https://abc.execute-api.us-east-1.amazonaws.com", "IDP_AUDIENCE": "bankagent",
       "IDP_KID": "lb-demo-1", "IDP_SIGNING_SECRET_ID": "lb-demo/idp-signing-key",
       "DEMO_USERS_S3_URI": "s3://serving-bucket/identity/demo_users.yaml", "IDP_DEMO_MODE": "1"}


def http_event(path, method="GET"):
    return {"version": "2.0", "routeKey": "$default", "rawPath": path, "rawQueryString": "",
            "headers": {"host": "abc.execute-api.us-east-1.amazonaws.com"},
            "requestContext": {"http": {"method": method, "path": path, "protocol": "HTTP/1.1", "sourceIp": "1.2.3.4",
                                        "userAgent": "pytest"}, "stage": "$default", "requestId": "r1",
                               "domainName": "abc.execute-api.us-east-1.amazonaws.com", "apiId": "abc"},
            "isBase64Encoded": False}


@pytest.fixture
def aws(monkeypatch):
    for k, v in {"AWS_ACCESS_KEY_ID": "t", "AWS_SECRET_ACCESS_KEY": "t", "AWS_REGION": "us-east-1",
                 "AWS_DEFAULT_REGION": "us-east-1", **ENV}.items():
        monkeypatch.setenv(k, v)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="serving-bucket")
        sm = boto3.client("secretsmanager", region_name="us-east-1")
        sm.create_secret(Name="lb-demo/idp-signing-key", SecretString=generate_keypair()[0])
        monkeypatch.setattr(lh, "_handler", None)
        yield s3


def test_discovery_and_jwks_served_from_secret_key(aws):
    aws.put_object(Bucket="serving-bucket", Key="identity/demo_users.yaml", Body=USERS_YAML.encode())
    r = lh.handler(http_event("/.well-known/openid-configuration"), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["issuer"] == ENV["IDP_ISSUER"]
    keys = json.loads(lh.handler(http_event("/jwks.json"), None)["body"])["keys"]
    assert len(keys) == 1 and keys[0]["kid"] == "lb-demo-1"


def test_demo_mode_serves_demo_users(aws):
    aws.put_object(Bucket="serving-bucket", Key="identity/demo_users.yaml", Body=USERS_YAML.encode())
    body = json.loads(lh.handler(http_event("/auth/demo-users"), None)["body"])
    assert [u["username"] for u in body] == ["demo01"]


def test_cold_start_failure_returns_503_and_retries(aws):
    r = lh.handler(http_event("/.well-known/openid-configuration"), None)  # users object not uploaded yet
    assert r["statusCode"] == 503 and json.loads(r["body"]) == {"error": "identity_unavailable"}
    assert lh._handler is None  # the failure is not cached
    aws.put_object(Bucket="serving-bucket", Key="identity/demo_users.yaml", Body=USERS_YAML.encode())
    assert lh.handler(http_event("/.well-known/openid-configuration"), None)["statusCode"] == 200


def test_bad_s3_uri_is_a_cold_start_failure(aws, monkeypatch):
    monkeypatch.setenv("DEMO_USERS_S3_URI", "https://not-s3/demo_users.yaml")
    assert lh.handler(http_event("/jwks.json"), None)["statusCode"] == 503
