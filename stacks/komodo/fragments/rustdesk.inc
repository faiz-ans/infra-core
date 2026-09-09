[[stack]]
name = "rustdesk"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/rustdesk"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
NAS_LAN_IP = [[NAS_LAN_IP]]
"""

# Off until restic-rest is on the IronWolf. Applying this now would crash-loop against :8000.
