[[stack]]
name = "homeassistant"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/homeassistant"
file_paths = ["compose.nfs.yaml"]
config_files = [
  { path = "ensure-http/http.yaml", requires = "Redeploy" },
  { path = "ensure-http/patch.py", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
NAS_LAN_IP = [[NAS_LAN_IP]]
"""

# Host stats for Homepage. LAN bind :61208; Caddy proxies glances2.<DOMAIN>.
# ResourceSync names are global — must not reuse "glances" from stacks-core.toml.
