#!/usr/bin/env bash
set -euo pipefail

APP_NAME="twitch-azurabridge"
BASE_DIR="/opt/custom-dockers"
APP_DIR="${BASE_DIR}/${APP_NAME}"
REPO_URL="${REPO_URL:-https://github.com/jamesking210/twitch-azurabridge.git}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this as root:"
  echo "  sudo su"
  echo "  bash install-on-linuxbox2.sh"
  exit 1
fi

echo "Installing basic packages..."
apt update
apt install -y git unzip curl ca-certificates

if ! command -v docker >/dev/null 2>&1; then
  echo
  echo "Docker was not found."
  echo "Install Docker first, then rerun this script."
  echo "On Ubuntu, Docker may already be installed on linuxbox2 because AzuraCast is running."
  exit 1
fi

mkdir -p "$BASE_DIR"

if [ -d "$APP_DIR" ]; then
  echo "Project folder already exists:"
  echo "  $APP_DIR"
  echo "Use refresh-from-github.sh if you want to redownload it."
  exit 1
fi

cd "$BASE_DIR"
git clone "$REPO_URL" "$APP_NAME"
cd "$APP_DIR"

cp .env.example .env

echo
echo "Edit .env now. Fill in Twitch client/secret and AzuraCast DJ passwords."
nano .env

docker compose up -d --build
docker logs -f twitch-azurabridge
