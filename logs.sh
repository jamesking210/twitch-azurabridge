#!/usr/bin/env bash
set -euo pipefail

echo "Following twitch-azurabridge logs. Press CTRL+C to stop watching logs."
docker logs -f twitch-azurabridge
