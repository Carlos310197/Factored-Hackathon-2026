#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ENV_FILE=../../../.env
env_get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2-; }

export AWS_PROFILE=hackathon-sso
export SNOWFLAKE_PASSWORD="$(python3 -c 'import pathlib, tomllib; p = pathlib.Path.home() / "Library/Application Support/snowflake/config.toml"; print(tomllib.loads(p.read_text())["connections"]["sbx"]["password"])')"
export TF_VAR_organizer_key_id="$(env_get AWS_ACCESS_KEY_ID)"
export TF_VAR_organizer_secret="$(env_get AWS_SECRET_ACCESS_KEY)"

terraform init -input=false
terraform "${TF_CMD:-apply}" "$@"
