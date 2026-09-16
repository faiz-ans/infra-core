#!/bin/bash
# Adventure Log's requests client uses certifi, not SSL_CERT_FILE, so Caddy
# tls internal fails Authelia discovery. Install sitecustomize first.
# Prefer PYTHONPATH: the image's site-packages may be read-only.
set -e
HOOKS=/tmp/oidc-hooks
mkdir -p "${HOOKS}"
cp /oidc-sitecustomize.py "${HOOKS}/sitecustomize.py"
export PYTHONPATH="${HOOKS}${PYTHONPATH:+:${PYTHONPATH}}"
python3 - <<'PY'
import pathlib, shutil, site
src = pathlib.Path("/oidc-sitecustomize.py")
for dest_dir in site.getsitepackages():
    try:
        dst = pathlib.Path(dest_dir) / "sitecustomize.py"
        shutil.copy(src, dst)
        print("adventurelog-oidc: installed", dst, flush=True)
    except OSError as exc:
        print("adventurelog-oidc: skip", dest_dir, exc, flush=True)
print("adventurelog-oidc: PYTHONPATH sitecustomize ready", flush=True)
PY
# aio entrypoint migrates, then exec "$@". Seed the SocialApp after migrate.
if [ "$#" -eq 0 ] || [ "$1" = "supervisord" ]; then
  exec /aio/entrypoint.sh bash -c \
    'python3 /oidc-seed.py || echo "adventurelog-oidc: seed failed (non-fatal)" >&2; exec supervisord -c /aio/supervisord.conf'
fi
exec /aio/entrypoint.sh "$@"
