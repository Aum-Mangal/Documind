#!/bin/sh
# Container entrypoint: make sure there is a secret key, migrate the database, start the API.
set -e

# Running locally needs no setup: without a SECRET_KEY, generate one on first start and keep it
# in /app/state (a Docker volume), so sign-ins survive restarts.
if [ -z "$SECRET_KEY" ]; then
    key_file=/app/state/secret_key
    if [ ! -s "$key_file" ]; then
        python -c "import secrets; print(secrets.token_urlsafe(48))" > "$key_file"
        chmod 600 "$key_file"
        echo "Generated a new SECRET_KEY in $key_file"
    fi
    SECRET_KEY=$(cat "$key_file")
    export SECRET_KEY
fi

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --proxy-headers --forwarded-allow-ips='*'
