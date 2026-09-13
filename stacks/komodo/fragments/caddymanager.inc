[[stack]]
name = "caddymanager"
deploy = false
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/caddymanager"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
CADDYMANAGER_JWT_SECRET = [[CADDYMANAGER_JWT_SECRET]]
"""

# Experiment. Leave deploy=false until you want a Caddy UI. GitOps still owns the Caddyfile.
