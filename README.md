# Twitch → AzuraCast Bridge — Foolproof Jim Downloads Setup

This project is okay to keep in your Downloads folder.

Default folder:

```text
/home/jim/Downloads/twitch-azurabridge
```

The commands below use `LINUX_USER=jim` as a variable, so later you can change only one line if the Linux username changes.

Your current AzuraCast setup stays as-is:

```text
AzuraCast local IP: 192.168.1.17
Live port: 8005
Streamer/DJ mount: /
```

This version is built to avoid the old ffmpeg error:

```text
No mountpoint (path) specified!
Broken pipe
```

It does that by using `AZURACAST_OUTPUT_MODE=auto`, which switches to HTTP PUT when the AzuraCast mount is `/`.

---

## 0. The variables used in every command

Use this at the top of your terminal session:

```bash
export LINUX_USER="jim"
export BASE_DIR="/home/${LINUX_USER}/Downloads"
export APP_NAME="twitch-azurabridge"
export APP_DIR="${BASE_DIR}/${APP_NAME}"
export REPO_URL="https://github.com/jamesking210/twitch-azurabridge.git"
```

If your GitHub repo URL is different, only change this line:

```bash
export REPO_URL="https://github.com/jamesking210/twitch-azurabridge.git"
```

---

## 1. First-time install from GitHub

Run this from your Ubuntu machine:

```bash
export LINUX_USER="jim"
export BASE_DIR="/home/${LINUX_USER}/Downloads"
export APP_NAME="twitch-azurabridge"
export APP_DIR="${BASE_DIR}/${APP_NAME}"
export REPO_URL="https://github.com/jamesking210/twitch-azurabridge.git"

mkdir -p "$BASE_DIR"
cd "$BASE_DIR" || exit 1

git clone "$REPO_URL" "$APP_NAME"
cd "$APP_DIR" || exit 1

cp .env.example .env
nano .env
```

Fill in these four lines:

```env
TWITCH_CLIENT_ID=your_twitch_client_id_here
TWITCH_CLIENT_SECRET=your_twitch_client_secret_here

AZURACAST_STREAMER_JIMBOSLICECHICAGO_PASSWORD=your_jimbo_dj_password_here
AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD=your_chuck_dj_password_here
```

Leave these alone:

```env
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
AZURACAST_AUTH_MODE=source_password
STREAMLINK_QUALITY=audio_only
```

Save nano:

```text
CTRL+O
ENTER
CTRL+X
```

Start it:

```bash
cd "$APP_DIR"
docker compose up -d --build
docker logs -f twitch-azurabridge
```

---

## 2. Normal restart after editing `.env`

Always run Docker Compose from the project folder.

```bash
export LINUX_USER="jim"
export APP_DIR="/home/${LINUX_USER}/Downloads/twitch-azurabridge"

cd "$APP_DIR" || exit 1
docker compose down
docker compose up -d --build
docker logs -f twitch-azurabridge
```

You can also use the helper script:

```bash
cd /home/jim/Downloads/twitch-azurabridge
bash restart-local.sh
```

---

## 3. Full Git redownload, while saving your `.env`

Use this when you want to blow away the old project folder and redownload the latest copy from GitHub.

This does five things:

1. Goes into the current project folder.
2. Runs `docker compose down` from the correct folder.
3. Backs up your real `.env` file.
4. Deletes and reclones the project from GitHub.
5. Restores `.env`, rebuilds, starts, then follows logs.

```bash
export LINUX_USER="jim"
export BASE_DIR="/home/${LINUX_USER}/Downloads"
export APP_NAME="twitch-azurabridge"
export APP_DIR="${BASE_DIR}/${APP_NAME}"
export REPO_URL="https://github.com/jamesking210/twitch-azurabridge.git"

mkdir -p "$BASE_DIR"

if [ -d "$APP_DIR" ]; then
  cd "$APP_DIR" || exit 1
  docker compose down || true

  if [ -f .env ]; then
    cp .env "${BASE_DIR}/${APP_NAME}.env.backup"
    echo "Saved .env backup to ${BASE_DIR}/${APP_NAME}.env.backup"
  fi
fi

cd "$BASE_DIR" || exit 1
rm -rf "$APP_NAME"
git clone "$REPO_URL" "$APP_NAME"
cd "$APP_DIR" || exit 1

if [ -f "${BASE_DIR}/${APP_NAME}.env.backup" ]; then
  cp "${BASE_DIR}/${APP_NAME}.env.backup" .env
  echo "Restored your saved .env"
else
  cp .env.example .env
  echo "No saved .env was found. Edit .env now."
  nano .env
fi

docker compose up -d --build
docker logs -f twitch-azurabridge
```

You can also use the helper script:

```bash
cd /home/jim/Downloads/twitch-azurabridge
bash refresh-from-github.sh
```

---

## 4. Quick status commands

Show the container:

```bash
docker ps --filter name=twitch-azurabridge
```

Show the last 200 log lines:

```bash
docker logs --tail=200 twitch-azurabridge
```

Follow live logs:

```bash
docker logs -f twitch-azurabridge
```

Stop the bridge:

```bash
export LINUX_USER="jim"
cd "/home/${LINUX_USER}/Downloads/twitch-azurabridge" || exit 1
docker compose down
```

---

## 5. Check `.env` without exposing passwords

Run this from the project folder:

```bash
export LINUX_USER="jim"
cd "/home/${LINUX_USER}/Downloads/twitch-azurabridge" || exit 1

echo "Safe settings:"
grep -E '^(TWITCH_USERNAMES|TWITCH_POLL_SECONDS|AZURACAST_HOST|AZURACAST_PORT|AZURACAST_MOUNT|AZURACAST_OUTPUT_MODE|AZURACAST_AUTH_MODE|STREAMLINK_QUALITY)=' .env || true

echo
echo "Secret settings exist, hidden:"
grep -E '^(TWITCH_CLIENT_ID|TWITCH_CLIENT_SECRET|AZURACAST_STREAMER_.*PASSWORD)=' .env | sed 's/=.*/=***hidden***/' || true
```

You should see:

```text
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
AZURACAST_AUTH_MODE=source_password
STREAMLINK_QUALITY=audio_only
```

---

## 6. What success looks like

When nobody is live:

```text
No priority Twitch channels are live
```

When Chuck is live:

```text
Starting live bridge: ChuckTheDJCa is On Twitch Live ...
Using AzuraCast streamer username: chuckthedjca
```

When Jimbo is live, Jimbo should win because he is first in:

```env
TWITCH_USERNAMES=jimboslicechicago,chuckthedjca
```

---

## 7. Troubleshooting broken pipe

The old bad output looked like this:

```text
No mountpoint (path) specified!
Error opening output icecast://...@192.168.1.17:8005/
Broken pipe
```

For your setup, keep this in `.env`:

```env
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
```

That makes the bridge use HTTP PUT for the `/` mount instead of ffmpeg's `icecast://` root mount.

If it still fails to authenticate, try this one-line change in `.env`:

```env
AZURACAST_AUTH_MODE=streamer_login
```

Then restart:

```bash
cd /home/jim/Downloads/twitch-azurabridge
docker compose down
docker compose up -d --build
docker logs -f twitch-azurabridge
```

---

## 8. Local IP note

Use this for your setup:

```env
AZURACAST_HOST=192.168.1.17
```

Do not use `localhost` unless the bridge container is running in host networking. Inside Docker, `localhost` usually means the bridge container itself, not your AzuraCast host.
