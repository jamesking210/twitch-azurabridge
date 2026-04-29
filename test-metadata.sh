#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/custom-dockers/twitch-azurabridge"
cd "$APP_DIR" || {
  echo "ERROR: Could not cd into $APP_DIR"
  exit 1
}

if [ ! -f .env ]; then
  echo "ERROR: .env missing"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

HOST="${AZURACAST_HOST:-192.168.1.17}"
PORT="${AZURACAST_PORT:-8005}"
MOUNT="${AZURACAST_MOUNT:-/}"
AUTH_MODE="${AZURACAST_AUTH_MODE:-source_password}"
SEP="${AZURACAST_SOURCE_PASSWORD_SEPARATOR:-:}"
SOURCE_USER="${AZURACAST_SOURCE_USER:-source}"
STREAMER_USER="${AZURACAST_STREAMER_CHUCKTHEDJCA_USERNAME:-chuckthedjca}"
STREAMER_PASS="${AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD:-}"
SONG="${1:-ChuckTheDJCA - Metadata Test}"

if [ -z "$STREAMER_PASS" ] || [ "$STREAMER_PASS" = "changeme" ]; then
  echo "ERROR: AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD is missing/changeme in .env"
  exit 1
fi

if [ "$AUTH_MODE" = "streamer_login" ]; then
  USER="$STREAMER_USER"
  PASS="$STREAMER_PASS"
else
  USER="$SOURCE_USER"
  PASS="${STREAMER_USER}${SEP}${STREAMER_PASS}"
fi

echo "Pushing metadata to ${HOST}:${PORT}${MOUNT}"
echo "Song: $SONG"
echo "Auth user: $USER"
echo

curl -v --max-time 10 -u "$USER:$PASS" \
  --get "http://${HOST}:${PORT}/admin/metadata" \
  --data-urlencode "mount=${MOUNT}" \
  --data-urlencode "mode=updinfo" \
  --data-urlencode "song=${SONG}"

echo
