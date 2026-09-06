[[stack]]
name = "transmute"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/transmute"
file_paths = ["compose.yaml"]
config_files = [
  { path = "entrypoint-oidc.sh", requires = "Redeploy" },
  { path = "sitecustomize-oidc.py", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
TRANSMUTE_AUTH_SECRET_KEY = [[TRANSMUTE_AUTH_SECRET_KEY]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""

# Local volume for Argos models. Caddy proxies :5000.
