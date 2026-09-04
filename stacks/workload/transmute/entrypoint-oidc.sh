#!/bin/bash
# Transmute's httpx uses certifi, not SSL_CERT_FILE, so Caddy tls internal
# fails discovery. Install sitecustomize before the app starts.
set -e
python - <<'PY'
import pathlib, shutil, site
src = pathlib.Path("/oidc-sitecustomize.py")
dst = pathlib.Path(site.getsitepackages()[0]) / "sitecustomize.py"
shutil.copy(src, dst)
print("transmute-oidc: installed", dst, flush=True)
PY
exec /bin/bash /app/entrypoint.sh
