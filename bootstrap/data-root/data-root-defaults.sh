# Shared defaults for DATA_ROOT host scripts (this reference site).
# New sites: set these from bootstrap step 0 (or export before running prep/layout).
# Sourced by data-root-prep.sh and data-root-layout.sh — do not run alone.

DATA_ROOT="${DATA_ROOT:-/srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
HOUSEHOLD=(faiz diana)
HTPC=periphery
ADMIN=pilot
SHARED_GROUP=sharedwrite
HTPC_GROUP=htpc

# Relative to shared/. Layout script root-owns these and stickies parents.
PROTECTED_SHARED=(
  photos
  media
  media/tv
  media/movies
  games
  games/web
  games/assets
  games/assets/launcher
  games/assets/collection
  games/assets/category
  games/assets/source
  games/roms
  games/steam
  games/steam/steamapps
  games/steam/steamapps/downloading
  games/steam/steamapps/temp
  games/steam/steamapps/workshop
  games/steam/steamapps/shadercache
  games/steam/steamapps/common
  files
  cameras
  cameras/exports
  cameras/clips
  cameras/clips/thumbs
  cameras/clips/review
  cameras/clips/cache
  cameras/clips/export
  cameras/recordings
  downloads
  downloads/complete
  downloads/incomplete
)
