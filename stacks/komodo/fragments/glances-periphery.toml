[[stack]]
name = "glances-periphery"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/glances"
file_paths = ["compose.periphery.yaml"]
config_files = [
  { path = "glances.conf", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
"""

# Local volume. Same wildcard as Core (*.DOMAIN → NAS_LAN_IP / Caddy).
# ResourceSync matches stacks by name globally — must not reuse "pihole" from stacks-core.toml.
