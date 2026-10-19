#!/bin/bash
# A Sablier stop during uv sync leaves a half-written pyproject.toml.
# The next start then fails before the server listens. Drop that env so setup writes it again.
set -euo pipefail
python3 - <<'PY'
import pathlib
import shutil

root = pathlib.Path("/app/whisperx-env")
if not root.is_dir():
    raise SystemExit(0)
try:
    import tomllib
except ImportError:
    raise SystemExit(0)
for path in list(root.rglob("pyproject.toml")):
    try:
        tomllib.loads(path.read_text())
    except Exception:
        shutil.rmtree(path.parent, ignore_errors=True)
PY
exec docker-entrypoint.sh /app/scriberr
