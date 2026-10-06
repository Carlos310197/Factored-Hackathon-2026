#!/usr/bin/env bash
# Values never touch argv, history or disk: silent prompt and openssl, both over stdin.
set -euo pipefail
export AWS_PROFILE=hackathon-sso AWS_REGION=us-east-1

put() { aws secretsmanager put-secret-value --secret-id "$1" --secret-string file:///dev/stdin --output text --query VersionId >/dev/null; }

read -r -s -p "Jev credential: " JEV; echo >&2
[ -n "$JEV" ] || { echo "empty Jev credential" >&2; exit 1; }
printf %s "$JEV" | put lb-demo/jev
unset JEV

openssl genrsa 2048 2>/dev/null | put lb-demo/idp-signing-key
echo "lb-demo/jev and lb-demo/idp-signing-key set" >&2
