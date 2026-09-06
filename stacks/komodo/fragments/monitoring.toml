[[stack]]
name = "monitoring"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/monitoring"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
GRAFANA_ADMIN_PASSWORD = [[GRAFANA_ADMIN_PASSWORD]]
OIDC_CLIENT_SECRET = [[OIDC_CLIENT_SECRET]]
"""

# Off until the 4TB IronWolf is the backup target. Do not apply this stack yet.
