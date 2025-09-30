#!/usr/bin/env bash
# TODO: Mark this file as executable (chmod +x scripts/dev_up.sh).

set -euo pipefail

docker compose up --build "$@"
