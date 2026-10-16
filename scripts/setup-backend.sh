#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "Instale uv: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.10 .venv
fi
uv pip sync --python .venv/bin/python backend/requirements-dev.lock
uv pip install --python .venv/bin/python --no-deps -e backend
.venv/bin/python -m pytest backend/tests -q
