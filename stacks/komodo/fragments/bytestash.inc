[[stack]]
name = "bytestash"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/bytestash"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
BYTESTASH_JWT_SECRET = [[BYTESTASH_JWT_SECRET]]
BYTESTASH_ALLOW_NEW_ACCOUNTS = [[BYTESTASH_ALLOW_NEW_ACCOUNTS]]
NAS_LAN_IP = [[NAS_LAN_IP]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""

# Host network. Not on edge. Do not port-forward 21115–21119; off-LAN is wg-easy.
