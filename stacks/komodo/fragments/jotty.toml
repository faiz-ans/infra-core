[[stack]]
name = "jotty"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/jotty"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
PUID = [[PUID]]
PGID = [[PGID]]
NAS_LAN_IP = [[NAS_LAN_IP]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""
