[[stack]]
name = "libretranslate"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/libretranslate"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
"""

# Local docstore volume. Caddy proxies :3003 (not SeaweedFS :8333).
