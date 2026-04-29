# Twitch → AzuraCast Bridge

This Docker project polls priority Twitch channels and relays the first live channel into AzuraCast as a Streamer/DJ live source.

Current defaults are set for:

- AzuraCast host: `192.168.1.17`
- AzuraCast live port: `8005`
- AzuraCast Streamer/DJ mount: `/`
- Priority order: `jimboslicechicago`, then `chuckthedjca`

## What changed in this version

You said you do **not** want to change anything in AzuraCast.

Your AzuraCast screen shows:

```text
Mount Name: /
Port: 8005
```

The earlier broken pipe came from ffmpeg trying to use this URL shape:

```text
icecast://user:password@192.168.1.17:8005/
```

ffmpeg's `icecast://` output treats a plain `/` root mount as no mountpoint and fails with:

```text
No mountpoint (path) specified!
Broken pipe
```

This version keeps AzuraCast's mount as `/`, but automatically uses **HTTP PUT** for the root mount instead of ffmpeg's `icecast://` protocol.

So you should not need to change the AzuraCast mount to `/live`.

## Install

```bash
cd /opt/custom-dockers
unzip twitch-azurabridge-root-mount.zip
cd twitch-azurabridge
cp .env.example .env
nano .env
```

Fill in:

```env
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
AZURACAST_STREAMER_JIMBOSLICECHICAGO_PASSWORD=your_jimbo_dj_password
AZURACAST_STREAMER_CHUCKTHEDJCA_PASSWORD=your_chuck_dj_password
```

Start it:

```bash
docker compose up -d --build
docker logs -f twitch-azurabridge
```

## Default `.env` settings for your AzuraCast box

```env
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/
AZURACAST_OUTPUT_MODE=auto
```

`AZURACAST_OUTPUT_MODE=auto` means:

```text
If mount is /      -> use HTTP PUT
If mount is /live  -> use icecast://
```

## Auth mode note

The default is:

```env
AZURACAST_AUTH_MODE=source_password
AZURACAST_SOURCE_USER=source
AZURACAST_SOURCE_PASSWORD_SEPARATOR=:
```

That builds the Icecast password the way AzuraCast shows it for Streamer/DJ accounts:

```text
dj_username:dj_password
```

If your AzuraCast setup only works with the streamer username and streamer password as normal login fields, change this:

```env
AZURACAST_AUTH_MODE=streamer_login
```

Then restart:

```bash
docker compose down
docker compose up -d --build
```

## Local IP note

Use this for your setup:

```env
AZURACAST_HOST=192.168.1.17
```

Do not use `localhost` unless the bridge container is running in host networking. Inside Docker, `localhost` usually means the bridge container itself, not your AzuraCast host.

## Priority behavior

This line controls priority:

```env
TWITCH_USERNAMES=jimboslicechicago,chuckthedjca
```

The first live channel wins. If both are live, `jimboslicechicago` wins and `chuckthedjca` is ignored until Jimbo goes offline.

## Useful commands

```bash
docker logs -f twitch-azurabridge
docker compose restart
docker compose down
docker compose up -d --build
```

Check port reachability from the host:

```bash
nc -vz 192.168.1.17 8005
```

## If it still fails

Try this one-line `.env` change first:

```env
AZURACAST_AUTH_MODE=streamer_login
```

Then rebuild/restart:

```bash
docker compose down
docker compose up -d --build
docker logs -f twitch-azurabridge
```
