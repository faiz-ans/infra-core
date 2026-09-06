[[stack]]
name = "authelia"
deploy = true
after = ["caddy"]
[stack.config]
server = "core"
repo = "faiz-ans/infra-core"
branch = "main"
run_directory = "stacks/platform/authelia"
file_paths = ["compose.yaml"]
config_files = [
  { path = "configuration.yml", requires = "Redeploy" },
]
webhook_enabled = false
poll_for_updates = true
environment = """
DOMAIN = [[DOMAIN]]
TZ = [[TZ]]
DATA_ROOT = [[DATA_ROOT]]
AUTHELIA_JWT_SECRET = [[AUTHELIA_JWT_SECRET]]
AUTHELIA_SESSION_SECRET = [[AUTHELIA_SESSION_SECRET]]
AUTHELIA_STORAGE_ENCRYPTION_KEY = [[AUTHELIA_STORAGE_ENCRYPTION_KEY]]
AUTHELIA_OIDC_HMAC_SECRET = [[AUTHELIA_OIDC_HMAC_SECRET]]
"""

# Name is global across ResourceSync files. The HTPC copy is "pihole-periphery".
