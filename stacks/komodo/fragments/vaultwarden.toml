[[stack]]
name = "vaultwarden"
deploy = true
after = ["caddy", "authelia"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/vaultwarden"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
VAULTWARDEN_ADMIN_TOKEN = [[VAULTWARDEN_ADMIN_TOKEN]]
SIGNUPS_ALLOWED = [[SIGNUPS_ALLOWED]]
"""
