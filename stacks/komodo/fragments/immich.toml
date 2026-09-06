[[stack]]
name = "immich"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/immich"
file_paths = ["compose.nfs.yaml"]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
DOMAIN = [[DOMAIN]]
NAS_LAN_IP = [[NAS_LAN_IP]]
NFS_EXPORT = [[NFS_EXPORT]]
NFS_USERS = [[NFS_USERS]]
IMMICH_DB_PASSWORD = [[IMMICH_DB_PASSWORD]]
"""
