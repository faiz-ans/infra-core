[[stack]]
name = "arr"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/arr"
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

# compose.nfs.yaml: downloads/media on NFS; /config is local (survives Core down).
