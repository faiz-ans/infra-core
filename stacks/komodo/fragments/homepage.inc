[[stack]]
name = "homepage"
deploy = true
after = ["caddy", "authelia", "glances"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/homepage"
file_paths = ["compose.yaml"]
config_files = [
  { path = "config/services.yaml", requires = "Redeploy" },
  { path = "config/settings.yaml", requires = "Redeploy" },
  { path = "config/docker.yaml", requires = "Redeploy" },
  { path = "config/widgets.yaml", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
HOMEPAGE_VAR_DOMAIN = [[DOMAIN]]
HOMEPAGE_VAR_HTPC_UPSTREAM = [[HTPC_UPSTREAM]]
HOMEPAGE_VAR_NAS_LAN_IP = [[NAS_LAN_IP]]
HOMEPAGE_VAR_PIHOLE_TOKEN = [[PIHOLE_WEBPASSWORD]]
HOMEPAGE_VAR_JELLYFIN_KEY = [[HOMEPAGE_VAR_JELLYFIN_KEY]]
HOMEPAGE_VAR_SONARR_KEY = [[HOMEPAGE_VAR_SONARR_KEY]]
HOMEPAGE_VAR_RADARR_KEY = [[HOMEPAGE_VAR_RADARR_KEY]]
HOMEPAGE_VAR_PROWLARR_KEY = [[HOMEPAGE_VAR_PROWLARR_KEY]]
HOMEPAGE_VAR_QBIT_USERNAME = [[HOMEPAGE_VAR_QBIT_USERNAME]]
HOMEPAGE_VAR_QBIT_PASSWORD = [[HOMEPAGE_VAR_QBIT_PASSWORD]]
HOMEPAGE_VAR_GRAFANA_KEY = [[HOMEPAGE_VAR_GRAFANA_KEY]]
HOMEPAGE_VAR_WGEASY_PASSWORD = [[HOMEPAGE_VAR_WGEASY_PASSWORD]]
WEATHER_LATITUDE = [[WEATHER_LATITUDE]]
WEATHER_LONGITUDE = [[WEATHER_LONGITUDE]]
HOMEPAGE_VAR_WEATHER_LATITUDE = [[WEATHER_LATITUDE]]
HOMEPAGE_VAR_WEATHER_LONGITUDE = [[WEATHER_LONGITUDE]]
HOMEPAGE_ALLOWED_HOSTS = dash.[[DOMAIN]]
"""
