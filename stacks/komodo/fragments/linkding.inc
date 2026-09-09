[[stack]]
name = "linkding"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/linkding"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
LINKDING_SUPERUSER_NAME = [[LINKDING_SUPERUSER_NAME]]
LINKDING_SUPERUSER_PASSWORD = [[LINKDING_SUPERUSER_PASSWORD]]
NAS_LAN_IP = [[NAS_LAN_IP]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""
