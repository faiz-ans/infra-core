[[stack]]
name = "n8n"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/n8n"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
N8N_ENCRYPTION_KEY = [[N8N_ENCRYPTION_KEY]]
"""

# Recordings on NFS (shared/cameras). /config is local. Caddy proxies :8971.
# MQTT :1883 is LAN-only for Home Assistant (not in Caddy).
