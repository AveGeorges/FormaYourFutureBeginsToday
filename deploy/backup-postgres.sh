#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.production.example to .env first." >&2
  exit 1
fi

set -a
source .env
set +a

mkdir -p backups
timestamp="$(date -u +%Y%m%d-%H%M%S)"
output="backups/forma-${timestamp}.sql.gz"

docker compose --env-file .env -f deploy/docker-compose.production.yml exec -T postgres \
  pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=plain \
  | gzip > "$output"

echo "Created $output"
