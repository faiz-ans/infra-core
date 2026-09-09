[[stack]]
name = "pihole"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/pihole"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
CORE_SERVER = [[CORE_SERVER]]
NAS_LAN_IP = [[NAS_LAN_IP]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
PIHOLE_WEBPASSWORD = [[PIHOLE_WEBPASSWORD]]
"""
