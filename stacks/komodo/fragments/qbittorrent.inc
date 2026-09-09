[[stack]]
name = "qbittorrent"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/qbittorrent"
file_paths = ["compose.nfs.yaml"]
config_files = [
  { path = "custom-cont-init.d/10-webui.sh", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
PUID = [[PUID]]
PGID = [[PGID]]
NAS_LAN_IP = [[NAS_LAN_IP]]
NFS_EXPORT = [[NFS_EXPORT]]
"""

# compose.nfs.yaml: photos/users on NFS; Postgres, Redis, ML, and upload are local.
