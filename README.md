# Twitch → AzuraCast Bridge

A small Docker project that monitors Twitch channels in priority order, pulls the first live channel's audio, and rebroadcasts it to AzuraCast/Icecast as a live streamer/DJ source.

This starter version does **not** require the AzuraCast API. It connects to AzuraCast the same way a DJ encoder like VirtualDJ, Mixxx, BUTT, or Rocket Broadcaster would connect.

## What it does

- Monitors Twitch channels in lowercase priority order.
- If `jimboslicechicago` and `chuckthedjca` are both live, `jimboslicechicago` wins.
- Pulls Twitch audio using Streamlink.
- Transcodes to MP3 with FFmpeg.
- Pushes to AzuraCast/Icecast using the matching streamer username/password.
- Sends text metadata like:

```text
JimboSliceChicago is On Twitch Live - Music - Dance EDM 2000s
```

## What it does not do yet

- It does not use the AzuraCast API.
- It does not automatically upload or change AzuraCast artwork.
- It does not manage schedules.
- It does not restream video, only audio.

For artwork, the recommended setup is to manually configure each AzuraCast streamer/DJ account with its own avatar/artwork inside AzuraCast.

## Files

```text
.
├── app/main.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup overview

You need:

1. AzuraCast reachable from `linuxbox2`.
2. AzuraCast streamer/DJ accounts created, for example:
   - `jimbo_twitch`
   - `chuck_twitch`
3. Twitch Developer app credentials:
   - `TWITCH_CLIENT_ID`
   - `TWITCH_CLIENT_SECRET`
4. Docker and Docker Compose on `linuxbox2`.

## AzuraCast setup

Create two lowercase streamer/DJ accounts in AzuraCast:

```text
jimbo_twitch
chuck_twitch
```

Use whatever passwords you want in AzuraCast, then put those same passwords in `.env`.

This project defaults to:

```env
AZURACAST_HOST=192.168.1.17
AZURACAST_PORT=8005
AZURACAST_MOUNT=/radio.mp3
```

Important: `AZURACAST_MOUNT` must match your working live streamer setup. If VirtualDJ is currently working with `/`, use `/`. If it uses `/radio.mp3`, use `/radio.mp3`.

## Twitch API setup

Create a Twitch app in the Twitch Developer Console and copy the Client ID and Client Secret into `.env`.

This project uses a Twitch app access token. It does not require each DJ to log in.

## Deploy on linuxbox2 from scratch

SSH into `linuxbox2`:

```bash
ssh jim@linuxbox2
```

Install Docker if needed:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

Log out and back in so your user can run Docker without `sudo`.

Clone your GitHub repo:

```bash
cd ~
git clone https://github.com/YOUR-GITHUB-USERNAME/twitch-azurabridge.git
cd twitch-azurabridge
```

Create your private `.env`:

```bash
cp .env.example .env
nano .env
```

Edit these values at minimum:

```env
TWITCH_CLIENT_ID=changeme
TWITCH_CLIENT_SECRET=changeme
AZURACAST_PASSWORD_JIMBOSLICECHICAGO=changeme
AZURACAST_PASSWORD_CHUCKTHEDJCA=changeme
AZURACAST_MOUNT=/radio.mp3
```

Start it:

```bash
docker compose up -d --build
```

Watch logs:

```bash
docker compose logs -f
```

Stop it:

```bash
docker compose down
```

Restart it:

```bash
docker compose restart
```

## Upload this project to GitHub

From the project folder on your computer or on `linuxbox2`:

```bash
git init
git add .
git commit -m "Initial Twitch AzuraCast bridge"
git branch -M main
git remote add origin https://github.com/YOUR-GITHUB-USERNAME/twitch-azurabridge.git
git push -u origin main
```

Do not commit `.env`. It is already ignored by `.gitignore`.

## Priority behavior

Priority is controlled here:

```env
TWITCH_PRIORITY=jimboslicechicago,chuckthedjca
```

That means:

```text
1. If jimboslicechicago is live, play Jimbo.
2. If Jimbo is offline and chuckthedjca is live, play Chuck.
3. If both are live, Jimbo wins.
4. If nobody is live, disconnect and AzuraCast AutoDJ should resume.
```

## Metadata format

Controlled by:

```env
METADATA_TEMPLATE={display_name} is On Twitch Live - {category} - {title}
```

Available fields:

```text
{login}
{display_name}
{category}
{title}
{tags}
```

Examples:

```text
JimboSliceChicago is On Twitch Live - Music - Dance EDM 2000s
ChuckTheDJCA is On Twitch Live - DJ - Yacht Rock Music
```

Text metadata support depends on how AzuraCast/Icecast handles metadata from a live source. This bridge attempts to pass metadata through FFmpeg using Icecast headers and stream metadata. If you later want richer now-playing behavior, add the AzuraCast API.

## Troubleshooting

### It says no channels are live

Check:

```bash
docker compose logs -f
```

Make sure:

- Twitch Client ID and Secret are correct.
- Twitch usernames in `TWITCH_PRIORITY` are lowercase and spelled correctly.
- The Twitch channels are actually live.

### It sees Twitch live but AzuraCast does not play it

Check:

- `AZURACAST_HOST=192.168.1.17`
- `AZURACAST_PORT=8005`
- `AZURACAST_MOUNT` matches your working VirtualDJ setup.
- The AzuraCast streamer username/password matches exactly.
- The streamer account is enabled in AzuraCast.
- Live streaming is enabled for the station.

### The Docker keeps reconnecting

Possible causes:

- Twitch stream went offline.
- Wrong AzuraCast mount.
- Wrong AzuraCast streamer password.
- AzuraCast live port is not reachable from `linuxbox2`.
- Another live source is already connected and AzuraCast is rejecting this one.

### Test network access from linuxbox2

```bash
ping 192.168.1.17
nc -vz 192.168.1.17 8005
```

If `nc` is not installed:

```bash
sudo apt install -y netcat-openbsd
```

## Safety notes

Only rebroadcast Twitch streams you own or have permission to rebroadcast. This tool is meant for your own DJMIXHUB workflow and approved DJs.
