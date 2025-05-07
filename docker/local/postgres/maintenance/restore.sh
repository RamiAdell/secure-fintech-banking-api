#!/usr/bin/env bash

set -o errexit

set -o pipefail

set -o nounset

working_dir="$(dirname ${0})"

source "${working_dir}/_sourced/constants.sh"
source "${working_dir}/_sourced/messages.sh"
source "${working_dir}/_sourced/ask.sh"

if [[ -z ${1+x} ]]; then
  message_error "Backup filename is not specified yet it a required parameter. Make sure you
  provide one and try again"
  exit 1
fi

backup_filename="${BACKUP_DIR_PATH}/${1}"

if [[ ! -f "${backup_filename}" ]]; then
  message_error "No backup with the specified filename found. Check out the 'backups' maintenance
   script output to see if there is one and try again."
  exit 1
fi

message_welcome "Restoring the '${POSTGRES_DB}' database from the '${backup_filename}' backup..."


if [[ "${POSTGRES_USER}" == "postgres" ]]; then
  message_error "Restoring as 'postgres' user is not supported. Assign 'POSTGRES_USER' env with
  another one and try again."
  exit 1
fi

export PGHOST="${POSTGRES_HOST}"
export PGPORT="${POSTGRES_PORT}"
export PGUSER="${POSTGRES_USER}"
export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGDATABASE="${POSTGRES_DB}"

message_info "This will drop the existing database. Are you sure you want to proceed?"

if ! yes_no "Continue with restore"; then
  message_info "Restore cancelled"
  exit 0
fi

message_info "Terminating existing database connections..."

psql -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM
pg_stat_activity WHERE pg_stat_activity.datname = '${POSTGRES_DB}' AND pid
<> pg_backend_pid();" postgres

sleep 2

message_info "Dropping the database..."

dropdb "${PGDATABASE}"

message_info "Creating a new database..."

createdb --owner="${POSTGRES_USER}"

message_info "Applying the backup to the new database..."

gunzip -c "${backup_filename}" | psql "${POSTGRES_DB}"

message_success "The '${POSTGRES_DB}' database has been restored from the '${backup_filename}'
backup."



