[[stack]]
name = "restic"
deploy = false
after = ["vaultwarden"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/restic"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
HTPC_UPSTREAM = [[HTPC_UPSTREAM]]
RESTIC_PASSWORD = [[RESTIC_PASSWORD]]
RESTIC_REST_USER = [[RESTIC_REST_USER]]
RESTIC_REST_PASSWORD = [[RESTIC_REST_PASSWORD]]
"""
