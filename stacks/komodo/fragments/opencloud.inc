[[stack]]
name = "opencloud"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/workload/opencloud"
file_paths = ["compose.yaml"]
config_files = [
  { path = "csp.yaml", requires = "Redeploy" },
  { path = "config/opencloud/proxy.yaml", requires = "Redeploy" },
  { path = "config/radicale/config", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
NAS_LAN_IP = [[NAS_LAN_IP]]
PUID = [[PUID]]
PGID = [[PGID]]
OPENCLOUD_ADMIN_PASSWORD = [[OPENCLOUD_ADMIN_PASSWORD]]
"""
