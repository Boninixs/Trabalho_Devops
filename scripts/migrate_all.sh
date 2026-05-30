#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in auth-service item-service matching-service recovery-case-service; do
  echo "==> ${service}: alembic upgrade head"
  (
    cd "${ROOT_DIR}/${service}"
    alembic upgrade head
  )
done
