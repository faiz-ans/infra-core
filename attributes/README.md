# Secrets

SET decrypts Age/SOPS files **on the operator machine** and installs Podman secrets on targets. Hosts do not receive a `site.env`.

Convention: keep `secrets.yaml` or `secrets.sops.yaml` beside local `site.yaml` (both gitignored). Schema: `examples/secrets.example.yaml`.

```bash
# encrypt (Age key stays on the runner)
sops --encrypt --age "$AGE_RECIPIENT" examples/secrets.example.yaml > secrets.sops.yaml
python3 ansible/site.py set --secrets secrets.sops.yaml
```

Catalog Quadlets still accept `${DOMAIN}`, `${DATA_ROOT}`, `${secrets.*}` after the resolver runs. Do not commit live IPs, domains, or secret values.
