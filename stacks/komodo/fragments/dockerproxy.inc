[[stack]]
name = "dockerproxy"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/dockerproxy"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
HTPC_UPSTREAM = [[HTPC_UPSTREAM]]
"""
