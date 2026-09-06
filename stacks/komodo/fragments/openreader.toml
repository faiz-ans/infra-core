[[stack]]
name = "openreader"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/openreader"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
OPENREADER_AUTH_SECRET = [[OPENREADER_AUTH_SECRET]]
"""

# Local SQLite volume. Caddy proxies :5678.
