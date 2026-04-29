#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/custom-dockers/twitch-azurabridge"

echo "=== Twitch -> AzuraCast Bridge Doctor ==="
echo

echo "1) Folder check"
if [ "$(pwd)" != "$APP_DIR" ]; then
  echo "WARNING: You are in: $(pwd)"
  echo "Expected: $APP_DIR"
  echo "Run: cd $APP_DIR"
else
  echo "OK: running from $APP_DIR"
fi

echo

echo "2) Docker check"
docker --version || true
docker compose version || true

echo

echo "3) Container check"
docker ps -a --filter name=twitch-azurabridge --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true

echo

echo "4) .env check"
if [ ! -f .env ]; then
  echo "ERROR: .env is missing. Run: cp .env.example .env && nano .env"
else
  echo "OK: .env exists"
  echo
  echo "Safe .env values:"
  grep -E '^(TWITCH_USERNAMES|TWITCH_POLL_SECONDS|AZURACAST_HOST|AZURACAST_PORT|AZURACAST_MOUNT|AZURACAST_OUTPUT_MODE|AZURACAST_AUTH_MODE|STREAMLINK_QUALITY|METADATA_UPDATE_ENABLED|METADATA_UPDATE_INTERVAL_SECONDS|METADATA_SONG_FORMAT)=' .env || true
  echo
  echo "Secret values hidden:"
  grep -E '^(TWITCH_CLIENT_ID|TWITCH_CLIENT_SECRET|AZURACAST_STREAMER_.*PASSWORD)=' .env | sed 's/=.*/=***hidden***/' || true
fi

echo

echo "5) AzuraCast port check"
HOST="192.168.1.17"
PORT="8005"
if [ -f .env ]; then
  HOST="$(grep -E '^AZURACAST_HOST=' .env | head -n1 | cut -d= -f2- || echo 192.168.1.17)"
  PORT="$(grep -E '^AZURACAST_PORT=' .env | head -n1 | cut -d= -f2- || echo 8005)"
fi

echo "Testing TCP ${HOST}:${PORT}"
if command -v nc >/dev/null 2>&1; then
  nc -vz "$HOST" "$PORT" || true
else
  timeout 5 bash -c "</dev/tcp/$HOST/$PORT" && echo "OK: port is reachable" || echo "WARNING: port test failed"
fi

echo

echo "6) AzuraCast public nowplaying check"
if command -v curl >/dev/null 2>&1; then
  curl -fsS --max-time 10 "http://192.168.1.17/api/nowplaying/djmixhub" | head -c 500 || true
  echo
else
  echo "curl not installed"
fi

echo

echo "7) Recent logs"
docker logs --tail=80 twitch-azurabridge || true
