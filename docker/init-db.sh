#!/usr/bin/env bash
set -e

# Initialize PostgreSQL with pgvector and non-owner application role
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Create non-owner application role for RLS enforcement
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'axiom_app') THEN
            CREATE ROLE axiom_app WITH LOGIN PASSWORD 'axiom_secret';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO axiom_app;
    GRANT USAGE ON SCHEMA public TO axiom_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO axiom_app;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO axiom_app;
EOSQL

