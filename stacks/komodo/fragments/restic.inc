# NAS client → HTPC REST on BACKUP_DRIVE. First-run: bootstrap/first-run/restic.md.

[[stack]]
name = "restic"
deploy = true
after = ["vaultwarden", "uptime-kuma"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/restic"
file_paths = ["compose.yaml"]
config_files = [
  { path = "backup.sh", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
HTPC_UPSTREAM = [[HTPC_UPSTREAM]]
RESTIC_PASSWORD = [[RESTIC_PASSWORD]]
RESTIC_REST_USER = [[RESTIC_REST_USER]]
RESTIC_REST_PASSWORD = [[RESTIC_REST_PASSWORD]]
UPTIME_KUMA_PUSH_URL = [[UPTIME_KUMA_PUSH_URL]]
"""
