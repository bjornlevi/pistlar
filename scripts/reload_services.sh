#!/usr/bin/env bash
set -euo pipefail

# Reloads the Pistlar gunicorn service and nginx so template/static changes take effect.

PISTLAR_SERVICE="pistlar.service"
NGINX_SERVICE="nginx.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root, e.g. sudo $0" >&2
  exit 1
fi

echo "Restarting ${PISTLAR_SERVICE}..."
systemctl restart "${PISTLAR_SERVICE}"

echo "Reloading ${NGINX_SERVICE} configuration..."
systemctl reload "${NGINX_SERVICE}"

echo "Done."
