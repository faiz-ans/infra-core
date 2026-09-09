[[stack]]
name = "restic-rest"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/restic-rest"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
BACKUP_DRIVE = [[BACKUP_DRIVE]]
RESTIC_REST_USER = [[RESTIC_REST_USER]]
RESTIC_REST_PASSWORD = [[RESTIC_REST_PASSWORD]]
"""
