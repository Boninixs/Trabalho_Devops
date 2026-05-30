#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_VENV_PYTHON="${ROOT_DIR}/.phase1-venv/bin/python"

cd "${ROOT_DIR}"

if [[ -n "${E2E_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="${E2E_PYTHON_BIN}"
elif [[ -x "${DEFAULT_VENV_PYTHON}" ]]; then
  PYTHON_BIN="${DEFAULT_VENV_PYTHON}"
else
  PYTHON_BIN="python3"
fi

if ! "${PYTHON_BIN}" -c "import aio_pika, httpx, psycopg, pytest" >/dev/null 2>&1; then
  echo "Dependencias E2E ausentes em ${PYTHON_BIN}." >&2
  echo "Use um ambiente com pytest, aio-pika, httpx e psycopg instalados ou defina E2E_PYTHON_BIN." >&2
  exit 1
fi

"${PYTHON_BIN}" -m pytest -m e2e tests/e2e -q "$@"
