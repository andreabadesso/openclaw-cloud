#!/bin/bash
set -e

# Create additional databases needed by services.
# POSTGRES_DB (openclaw_cloud) is created automatically by the postgres image.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE nango;
    GRANT ALL PRIVILEGES ON DATABASE nango TO $POSTGRES_USER;
EOSQL
