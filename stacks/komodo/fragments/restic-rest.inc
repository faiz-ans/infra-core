# HTPC REST on the 4TB USB (BACKUP_DRIVE). Not the IronWolf. bootstrap/first-run/restic.md.

[[stack]]
name = "restic-rest"
deploy = true
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
