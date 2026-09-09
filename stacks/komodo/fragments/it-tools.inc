[[stack]]
name = "it-tools"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/it-tools"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
"""
