#!/bin/bash
# Transmute's httpx uses certifi, not SSL_CERT_FILE, so Caddy tls internal
# fails discovery. Install sitecustomize before the app starts.
# Prefer PYTHONPATH: the image's site-packages may be read-only.
#
# DrawioConverter.can_register() runs `/opt/drawio/drawio --version` at boot.
# That Electron binary crashes WSL2 and writes multi-GB dumps to
# %LOCALAPPDATA%\Temp\wsl-crashes (wsl-crash-*-_opt_drawio_drawio-*.dmp).
set -e
if [[ -x /opt/drawio/drawio && ! -x /opt/drawio/drawio.real ]]; then
  mv /opt/drawio/drawio /opt/drawio/drawio.real
  cat > /opt/drawio/drawio <<'EOF'
#!/bin/bash
for arg in "$@"; do
  if [[ "$arg" == "--version" ]]; then
    echo "31.4.5"
    exit 0
  fi
done
exec /opt/drawio/drawio.real --disable-gpu --disable-dev-shm-usage --disable-software-rasterizer "$@"
EOF
  chmod +x /opt/drawio/drawio
  echo "transmute-oidc: wrapped /opt/drawio/drawio (WSL --version stub)" >&2
fi
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
