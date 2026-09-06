[[stack]]
name = "gitea"
deploy = true
after = ["caddy", "authelia"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/gitea"
file_paths = ["compose.yaml"]
config_files = [
  { path = "entrypoint-oidc.sh", requires = "Redeploy" },
  { path = "seed-oidc.sh", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
NAS_LAN_IP = [[NAS_LAN_IP]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""
