#!/bin/sh
# Create agent_pod when the bootstrap superuser is not agent_pod (optional compose layout).
# When POSTGRES_USER=agent_pod, the official Postgres image already created the role
# with POSTGRES_PASSWORD before init scripts run.
set -eu

pod_user="${POSTGRES_POD_USER:-agent_pod}"

if [ "${POSTGRES_USER}" = "${pod_user}" ]; then
    exit 0
fi

psql -v ON_ERROR_STOP=1 \
    -v "pod_user=${pod_user}" \
    -v "pod_password=${POSTGRES_PASSWORD}" \
    --username "${POSTGRES_USER}" \
    --dbname "${POSTGRES_DB}" <<'EOSQL'
DO $$
DECLARE
    role_name text := :'pod_user';
    role_password text := :'pod_password';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
        EXECUTE format('CREATE USER %I WITH PASSWORD %L', role_name, role_password);
    ELSE
        EXECUTE format('ALTER USER %I WITH PASSWORD %L', role_name, role_password);
    END IF;
END
$$;

GRANT agent_app TO :"pod_user";
EOSQL
