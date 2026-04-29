# Twitch → AzuraCast Bridge

Docker bridge for linuxbox2 that watches priority Twitch channels and relays the first live channel into AzuraCast as a Streamer/DJ live source.

This project is now standardized around this folder:

```text
/opt/custom-dockers/twitch-azurabridge
```

Default target:

```text
AzuraCast LAN IP: 192.168.1.17
Streamer/DJ port: 8005
Streamer/DJ mount: /
```

## What this fixes

### 1. Broken pipe / no mountpoint

AzuraCast currently shows the Streamer/DJ mount as `/`.

ffmpeg's normal `icecast://` output does not like a plain root mount and can fail with:

```text
No mountpoint (path) specified!
Broken pipe
```

This bridge keeps AzuraCast unchanged and uses HTTP PUT automatically when the mount is `/`:

```env
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
```

### 2. Wrong artist/title/art on the AzuraCast public player

If Chuck is live but the player still says Jimbo, the audio source is connected correctly but the public player metadata is stale.

This version pushes live metadata while the stream is running:

```text
Artist = Twitch display name
Title  = Twitch stream title
```

Example:

```text
ChuckTheDJCA - Tuesday Nite Pop Up
```

AzuraCast's public Now Playing data includes both the current song and live DJ state, so this bridge keeps the current song updated while the live DJ connection is active.

## First install on linuxbox2

You said you are okay installing as `sudo su`.

```bash
sudo su
mkdir -p /opt/custom-dockers
cd /opt/custom-dockers

git clone https://github.com/jamesking210/twitch-azurabridge.git
cd /opt/custom-dockers/twitch-azurabridge

cp .env.example .env
nano .env
```

Fill in your real secrets:

```env
TWITCH_CLIENT_ID=your_twitch_client_id
TWITCH_CLIENT_SECRET=your_twitch_client_secret

AZURACAST_STREAMER_JIMBOSLICECHICAGO_PASSWORD=your_jimbo_dj_password
AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD=your_chuck_dj_password
```

Leave these alone for linuxbox2:

```env
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
AZURACAST_AUTH_MODE=source_password
STREAMLINK_QUALITY=audio_only
METADATA_UPDATE_ENABLED=true
METADATA_SONG_FORMAT={display_name} - {title}
```

Start it:

```bash
cd /opt/custom-dockers/twitch-azurabridge
docker compose up -d --build
docker logs -f twitch-azurabridge
```

## Normal restart

```bash
sudo su
cd /opt/custom-dockers/twitch-azurabridge
docker compose down
docker compose up -d --build
docker logs -f twitch-azurabridge
```

Or:

```bash
sudo su
cd /opt/custom-dockers/twitch-azurabridge
bash restart-local.sh
```

## Full refresh from GitHub while saving `.env`

This is the safest "blow it away and redownload it" command.

```bash
sudo su
cd /opt/custom-dockers/twitch-azurabridge
bash refresh-from-github.sh
```

That script does this:

1. Runs `docker compose down` from the correct folder.
2. Backs up `/opt/custom-dockers/twitch-azurabridge/.env`.
3. Deletes the project folder.
4. Clones a fresh copy from GitHub.
5. Restores `.env`.
6. Rebuilds and starts the container.
7. Runs `docker logs -f twitch-azurabridge`.

## Useful commands

Follow logs:

```bash
cd /opt/custom-dockers/twitch-azurabridge
bash logs.sh
```

Run the local doctor:

```bash
cd /opt/custom-dockers/twitch-azurabridge
bash doctor.sh
```

Push a manual metadata test to AzuraCast:

```bash
cd /opt/custom-dockers/twitch-azurabridge
bash test-metadata.sh "ChuckTheDJCA - Metadata Test"
```

Show container status:

```bash
docker ps --filter name=twitch-azurabridge
```

Show last 200 log lines:

```bash
docker logs --tail=200 twitch-azurabridge
```

## Success logs

When nobody is live:

```text
No priority Twitch channels are live
```

When Chuck is live:

```text
Starting live bridge: ChuckTheDJCA is On Twitch Live ...
Using AzuraCast streamer username: chuckthedjca
Using metadata song: ChuckTheDJCA - Tuesday Nite Pop Up
Updated AzuraCast metadata: ChuckTheDJCA - Tuesday Nite Pop Up
```

## If audio works but metadata is still wrong

First check the logs:

```bash
docker logs --tail=200 twitch-azurabridge
```

If you see:

```text
Metadata update failed
```

try this one-line change in `.env`:

```env
AZURACAST_AUTH_MODE=streamer_login
```

Then restart:

```bash
cd /opt/custom-dockers/twitch-azurabridge
docker compose down
docker compose up -d --build
docker logs -f twitch-azurabridge
```

If that does not work, switch it back:

```env
AZURACAST_AUTH_MODE=source_password
```

## Priority order

This controls who wins when multiple Twitch channels are live:

```env
TWITCH_USERNAMES=jimboslicechicago,chuckthedjca
```

Jimbo wins over Chuck because Jimbo is first.

## Local IP note

Use the LAN IP:

```env
AZURACAST_HOST=192.168.1.17
```

Do not use `localhost` from inside Docker. Inside a container, `localhost` usually means the container itself, not the host running AzuraCast.
