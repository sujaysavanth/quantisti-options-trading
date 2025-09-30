#!/usr/bin/env bash
# TODO: Mark this file as executable (chmod +x scripts/dev_down.sh).

set -euo pipefail

docker compose down -v "$@"
