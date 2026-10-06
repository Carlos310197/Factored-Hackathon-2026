"""The identities file names dataset customer ids, so it is read from S3, never baked into the image.
A failed cold start answers 503 and is retried on the next request."""
import logging
import os
import tempfile
from pathlib import Path

import boto3
from cryptography.hazmat.primitives import serialization
from mangum import Mangum

from bankagent.identity.app import create_app
from bankagent.identity.users import load_users

log = logging.getLogger(__name__)
_handler = None
UNAVAILABLE = {"statusCode": 503, "headers": {"content-type": "application/json"},
               "body": '{"error": "identity_unavailable"}'}


def _split_s3(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://") or "/" not in uri[5:]:
        raise ValueError(f"not an s3:// object URI: {uri!r}")
    bucket, key = uri[5:].split("/", 1)
    return bucket, key


def build(env=os.environ, s3=None, secrets=None) -> Mangum:
    region = env.get("AWS_REGION", "us-east-1")
    s3 = s3 or boto3.client("s3", region_name=region)
    secrets = secrets or boto3.client("secretsmanager", region_name=region)
    private_pem = secrets.get_secret_value(SecretId=env["IDP_SIGNING_SECRET_ID"])["SecretString"]
    public_pem = serialization.load_pem_private_key(private_pem.encode(), None).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    bucket, key = _split_s3(env["DEMO_USERS_S3_URI"])
    path = Path(tempfile.gettempdir()) / "demo_users.yaml"
    path.write_bytes(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
    app = create_app(load_users(str(path)), private_pem, public_pem, env.get("IDP_KID", "idp-1"), env["IDP_ISSUER"],
                     env.get("IDP_AUDIENCE", "bankagent"), demo_mode=env.get("IDP_DEMO_MODE") == "1")
    return Mangum(app, lifespan="off")


def handler(event, context):
    global _handler
    if _handler is None:
        try:
            _handler = build()
        except Exception:
            log.exception("identity cold start failed")
            return UNAVAILABLE
    return _handler(event, context)
