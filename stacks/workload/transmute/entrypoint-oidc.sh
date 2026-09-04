#!/bin/bash
# Transmute's httpx uses certifi, not SSL_CERT_FILE, so Caddy tls internal
# fails discovery. Install sitecustomize before the app starts.
# Prefer PYTHONPATH: the image's site-packages may be read-only.
set -e
HOOKS=/tmp/oidc-hooks
mkdir -p "${HOOKS}"
cp /oidc-sitecustomize.py "${HOOKS}/sitecustomize.py"
export PYTHONPATH="${HOOKS}${PYTHONPATH:+:${PYTHONPATH}}"
python - <<'PY'
import pathlib, shutil, site
src = pathlib.Path("/oidc-sitecustomize.py")
for dest_dir in site.getsitepackages():
    try:
        dst = pathlib.Path(dest_dir) / "sitecustomize.py"
        shutil.copy(src, dst)
        print("transmute-oidc: installed", dst, flush=True)
    except OSError as exc:
        print("transmute-oidc: skip", dest_dir, exc, flush=True)
print("transmute-oidc: PYTHONPATH sitecustomize ready", flush=True)
PY
exec /bin/bash /app/entrypoint.sh
