[[stack]]
name = "adventurelog"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/adventurelog"
file_paths = ["compose.yaml"]
config_files = [
  { path = "entrypoint-oidc.sh", requires = "Redeploy" },
  { path = "sitecustomize-oidc.py", requires = "Redeploy" },
  { path = "seed-oidc.py", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
ADVENTURELOG_POSTGRES_PASSWORD = [[ADVENTURELOG_POSTGRES_PASSWORD]]
ADVENTURELOG_ADMIN_PASSWORD = [[ADVENTURELOG_ADMIN_PASSWORD]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""

# Local volumes for SQLite and Whisper models. Caddy proxies :8085.
