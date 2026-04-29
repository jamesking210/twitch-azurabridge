#!/usr/bin/env bash
set -euo pipefail

APP_NAME="twitch-azurabridge"
BASE_DIR="/opt/custom-dockers"
APP_DIR="${BASE_DIR}/${APP_NAME}"
REPO_URL="${REPO_URL:-https://github.com/jamesking210/twitch-azurabridge.git}"
BACKUP_DIR="/root/${APP_NAME}-backups"
BACKUP_ENV="${BACKUP_DIR}/.env.$(date +%Y%m%d-%H%M%S).backup"
LATEST_ENV="${BACKUP_DIR}/.env.latest"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this as root, for example:"
  echo "  sudo su"
  echo "  cd ${APP_DIR}"
  echo "  bash refresh-from-github.sh"
  exit 1
fi

mkdir -p "$BASE_DIR" "$BACKUP_DIR"

if [ -d "$APP_DIR" ]; then
  echo "Stopping existing Docker stack from the correct folder..."
  cd "$APP_DIR" || exit 1
  docker compose down || true

  if [ -f .env ]; then
    cp .env "$BACKUP_ENV"
    cp .env "$LATEST_ENV"
    echo "Backed up .env to:"
    echo "  $BACKUP_ENV"
  else
    echo "WARNING: no .env found to back up."
  fi
fi

echo "Deleting old project folder..."
cd "$BASE_DIR" || exit 1
rm -rf "$APP_NAME"

echo "Cloning fresh project from GitHub..."
git clone "$REPO_URL" "$APP_NAME"
cd "$APP_DIR" || exit 1

if [ -f "$LATEST_ENV" ]; then
  cp "$LATEST_ENV" .env
  echo "Restored saved .env"
else
  cp .env.example .env
  echo "No saved .env found. Opening nano so you can fill it in."
  nano .env
fi

echo "Building and starting..."
docker compose up -d --build

echo "Following logs. Press CTRL+C to stop watching logs."
docker logs -f twitch-azurabridge
