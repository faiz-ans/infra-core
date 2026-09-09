[[stack]]
name = "jellyfin"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/jellyfin"
file_paths = ["compose.nfs.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
PUID = [[PUID]]
PGID = [[PGID]]
NAS_LAN_IP = [[NAS_LAN_IP]]
NFS_EXPORT = [[NFS_EXPORT]]
"""

# Local volume only. Setup wizard talks to Jellyfin/Radarr/Sonarr over HTPC published ports.
