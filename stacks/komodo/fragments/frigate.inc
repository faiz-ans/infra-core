[[stack]]
name = "frigate"
deploy = false
[stack.config]
server = "periphery"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/frigate"
file_paths = ["compose.nfs.yaml"]
config_files = [
  { path = "seed/config.yml", requires = "Redeploy" },
  { path = "mosquitto/mosquitto.conf", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
TZ = [[TZ]]
NAS_LAN_IP = [[NAS_LAN_IP]]
NFS_EXPORT = [[NFS_EXPORT]]
"""

# HA /config is a local volume. trusted_proxies is written at container start (ensure-http/).
