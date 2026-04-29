# Twitch → AzuraCast Bridge

This project watches a priority list of Twitch channels, picks the first one that is live, pulls the audio with Streamlink, and sends it into AzuraCast through FFmpeg.

It is built for simple self-hosted Docker deployment and is meant to live in a stable path like:

```text
/opt/custom-dockers/twitch-azurabridge
```

## What it does

- polls Twitch for a priority-ordered list of channels
- bridges the first live channel into AzuraCast
- supports per-channel Streamer/DJ credentials
- handles AzuraCast root mount `/` safely with automatic HTTP PUT fallback
- restarts cleanly when the selected live channel changes

## Project layout

- `app/main.py`: bridge logic
- `.env.example`: environment settings and examples
- `Dockerfile`: runtime image
- `docker-compose.yml`: local and production container config
- `requirements.txt`: Python dependencies

## Config pattern

The bridge reads runtime settings from `.env` through Docker Compose.

Start by copying:

```bash
cp .env.example .env
```

Then fill in:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`
- `TWITCH_USERNAMES`
- `AZURACAST_HOST`
- `AZURACAST_PORT`
- `AZURACAST_STREAMER_<CHANNEL>_PASSWORD`

The sample file already includes sane defaults for:

- `AZURACAST_MOUNT=/`
- `AZURACAST_OUTPUT_MODE=auto`
- `AZURACAST_AUTH_MODE=source_password`
- `STREAMLINK_QUALITY=audio_only`

## Recommended deploy path on Ubuntu

Use a stable shared location instead of `Downloads`:

```bash
sudo mkdir -p /opt/custom-dockers
sudo chown "$USER":"$USER" /opt/custom-dockers
cd /opt/custom-dockers
```

## First-time install on Ubuntu

### 1. Install Docker and Git

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clone the repo

```bash
sudo mkdir -p /opt/custom-dockers
sudo chown "$USER":"$USER" /opt/custom-dockers
cd /opt/custom-dockers
git clone https://github.com/jamesking210/twitch-azurabridge.git
cd twitch-azurabridge
```

### 3. Create `.env`

```bash
cp .env.example .env
nano .env
```

Minimum secrets to fill in:

```env
TWITCH_CLIENT_ID=your_twitch_client_id_here
TWITCH_CLIENT_SECRET=your_twitch_client_secret_here
AZURACAST_STREAMER_JIMBOSLICECHICAGO_PASSWORD=your_jimbo_dj_password_here
AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD=your_chuck_dj_password_here
```

### 4. Build and start

```bash
docker compose up -d --build
docker compose ps
docker logs -f twitch-azurabridge
```

## Updating after a GitHub push

```bash
cd /opt/custom-dockers/twitch-azurabridge
git pull origin main
docker compose up -d --build
docker compose ps
```

## If you only changed `.env`

```bash
cd /opt/custom-dockers/twitch-azurabridge
nano .env
docker compose up -d --build
```

## Moving an existing install out of Downloads

If the current live copy is in `/home/jim/Downloads/twitch-azurabridge`, move it like this:

```bash
sudo mkdir -p /opt/custom-dockers
sudo chown "$USER":"$USER" /opt/custom-dockers
mv /home/jim/Downloads/twitch-azurabridge /opt/custom-dockers/
cd /opt/custom-dockers/twitch-azurabridge
docker compose up -d --build
docker compose ps
```

## Full fresh re-clone while keeping `.env`

```bash
cp /opt/custom-dockers/twitch-azurabridge/.env /tmp/twitch-azurabridge.env
cd /opt/custom-dockers
rm -rf twitch-azurabridge
git clone https://github.com/jamesking210/twitch-azurabridge.git
cd twitch-azurabridge
cp /tmp/twitch-azurabridge.env .env
docker compose up -d --build
docker compose ps
docker logs -f twitch-azurabridge
```

## Common commands

Show the container:

```bash
docker ps --filter name=twitch-azurabridge
```

Show recent logs:

```bash
docker logs --tail=200 twitch-azurabridge
```

Follow logs:

```bash
docker logs -f twitch-azurabridge
```

Stop the bridge:

```bash
cd /opt/custom-dockers/twitch-azurabridge
docker compose down
```

## Safe `.env` check

From the project folder:

```bash
echo "Safe settings:"
grep -E '^(TWITCH_USERNAMES|TWITCH_POLL_SECONDS|AZURACAST_HOST|AZURACAST_PORT|AZURACAST_MOUNT|AZURACAST_OUTPUT_MODE|AZURACAST_AUTH_MODE|STREAMLINK_QUALITY)=' .env || true

echo
echo "Secret settings exist, hidden:"
grep -E '^(TWITCH_CLIENT_ID|TWITCH_CLIENT_SECRET|AZURACAST_STREAMER_.*PASSWORD)=' .env | sed 's/=.*/=***hidden***/' || true
```

## Expected behavior

When nobody is live:

```text
No priority Twitch channels are live
```

When a channel is selected:

```text
Starting live bridge: ChuckTheDJCa is On Twitch Live ...
Using AzuraCast streamer username: chuckthedjca
```

Priority comes from `TWITCH_USERNAMES`. The first live channel in that list wins.

## Notes on AzuraCast output mode

For an AzuraCast mount of `/`, keep:

```env
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
```

That avoids FFmpeg's root-mount `icecast://` problem by switching to HTTP PUT automatically.

If authentication ever fails with the source-password format, try:

```env
AZURACAST_AUTH_MODE=streamer_login
```

## Local IP note

Inside Docker, `localhost` usually means the bridge container itself, not your AzuraCast server.

Use your actual AzuraCast host or LAN IP, for example:

```env
AZURACAST_HOST=192.168.1.17
```
