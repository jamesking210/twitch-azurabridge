#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/custom-dockers/twitch-azurabridge"

cd "$APP_DIR" || {
  echo "ERROR: Could not cd into $APP_DIR"
  exit 1
}

echo "Stopping old container..."
docker compose down || true

echo "Building and starting..."
docker compose up -d --build

echo "Following logs. Press CTRL+C to stop watching logs."
docker logs -f twitch-azurabridge
