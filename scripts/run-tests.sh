#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
CONDA_ENV="${CONDA_ENV:-monitor_backend}"
RUN_BACKEND=1
RUN_FRONTEND=1
INSTALL=0

usage() {
  printf '%s\n' "Usage: $0 [all|backend|frontend] [--install]"
  printf '%s\n' "Set CONDA_ENV to select the backend Conda environment."
}

for argument in "$@"; do
  case "$argument" in
    all) RUN_BACKEND=1; RUN_FRONTEND=1 ;;
    backend) RUN_BACKEND=1; RUN_FRONTEND=0 ;;
    frontend) RUN_BACKEND=0; RUN_FRONTEND=1 ;;
    --install) INSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Required command not found: %s\n' "$1" >&2
    exit 1
  }
}

if (( RUN_BACKEND )); then
  require_command conda
  if (( INSTALL )); then
    conda run --no-capture-output -n "$CONDA_ENV" python -m pip install -r "$ROOT_DIR/backend/requirements.txt" pytest
  fi
  PYTHONPATH="$ROOT_DIR/backend" conda run --no-capture-output -n "$CONDA_ENV" python -m pytest "$ROOT_DIR/backend/tests" -q
  PYTHONPATH="$ROOT_DIR/backend" conda run --no-capture-output -n "$CONDA_ENV" python -m compileall -q "$ROOT_DIR/backend"
fi

if (( RUN_FRONTEND )); then
  require_command node
  require_command npm
  if (( INSTALL )); then
    (
      cd "$ROOT_DIR/frontend"
      npm ci
    )
  fi
  (
    cd "$ROOT_DIR/frontend"
    test -x node_modules/.bin/vue-tsc || {
      printf '%s\n' 'Frontend dependencies are missing; rerun with --install.' >&2
      exit 1
    }
    npm run build
    npm run test:e2e
  )
fi
