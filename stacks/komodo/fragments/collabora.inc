[[stack]]
name = "collabora"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/collabora"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
"""

# Local volumes for PostGIS and media. Caddy proxies :8015.
