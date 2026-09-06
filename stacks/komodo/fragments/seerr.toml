[[stack]]
name = "seerr"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/seerr"
file_paths = ["compose.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
"""

# compose.nfs.yaml: media/downloads on NFS; Sonarr/Radarr/Prowlarr /config is local (SQLite).
