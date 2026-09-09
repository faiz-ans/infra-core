#!/bin/sh
# Copy git images into the persistent DATA_ROOT mount before Next.js starts.
# Empty Komodo clones bind-mount an empty ./images; DATA_ROOT keeps a prior copy.
# docker-entrypoint.sh then runs the image CMD (node server.js).
mkdir -p /app/public/images
if [ -d /git-images ]; then
  cp -an /git-images/. /app/public/images/ 2>/dev/null || true
fi
chmod -R a+rX /app/public/images 2>/dev/null || true
exec /usr/local/bin/docker-entrypoint.sh "$@"
