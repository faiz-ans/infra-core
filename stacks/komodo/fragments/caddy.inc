[[stack]]
name = "caddy"
deploy = true
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/caddy"
file_paths = ["compose.yaml"]
config_files = [
  { path = "Caddyfile", requires = "Redeploy" },
  { path = "entrypoint.sh", requires = "Redeploy" },
  { path = "export-ca.sh", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
HTPC_UPSTREAM = [[HTPC_UPSTREAM]]
NAS_LAN_IP = [[NAS_LAN_IP]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
"""
