[[stack]]
name = "glances"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/glances"
file_paths = ["compose.yaml"]
config_files = [
  { path = "glances.conf", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
"""
