[[stack]]
name = "wireguard"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/wireguard"
file_paths = ["compose.yaml"]
config_files = [
  { path = "entrypoint.sh", requires = "Redeploy" },
  { path = "seed-mtu.mjs", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
WG_HOST = [[WG_HOST]]
WG_UI_PASSWORD = [[WG_UI_PASSWORD]]
"""
