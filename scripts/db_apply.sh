#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is not set. Please export it before running this script." >&2
  exit 1
fi

shopt -s nullglob
sql_files=(schema/sql/*.sql)
if [ ${#sql_files[@]} -eq 0 ]; then
  echo "No SQL files found in schema/sql." >&2
  exit 1
fi

for file in "${sql_files[@]}"; do
  echo "Applying $file"
  if command -v psql >/dev/null 2>&1; then
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
  else
    if ! command -v docker >/dev/null 2>&1; then
      echo "psql not found and docker is unavailable. Cannot apply $file." >&2
      exit 1
    fi
    docker run --rm \
      -e DATABASE_URL="$DATABASE_URL" \
      -v "$PWD:/work" \
      -w /work \
      postgres:16 \
      psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
  fi
done

echo "Done."
