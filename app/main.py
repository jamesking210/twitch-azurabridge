#!/usr/bin/env python3
"""
Twitch → AzuraCast/Icecast bridge.

Monitors Twitch channels in priority order, pulls the first live channel's audio
with Streamlink, transcodes it with FFmpeg, and pushes it to AzuraCast as a live
streamer/DJ source.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests


APP_NAME = "twitch-azurabridge"
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_STREAMS_URL = "https://api.twitch.tv/helix/streams"


def log(message: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Missing required environment variable: {name}")
    return "" if value is None else value


def parse_bool(value: str, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def channel_env_key(channel: str) -> str:
    """Make jimboslicechicago -> JIMBOSLICECHICAGO for env var suffixes."""
    return re.sub(r"[^A-Z0-9]", "", channel.upper())


def normalize_mount(mount: str) -> str:
    mount = mount.strip() or "/"
    if not mount.startswith("/"):
        mount = "/" + mount
    return mount


def split_csv(value: str) -> List[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


@dataclass
class ChannelConfig:
    twitch_login: str
    azuracast_user: str
    azuracast_password: str


@dataclass
class LiveStream:
    login: str
    display_name: str
    title: str
    category: str
    tags: List[str]
    viewer_count: Optional[int] = None


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        log("Getting Twitch app access token")
        response = requests.post(
            TWITCH_TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._access_token

    def get_live_streams(self, logins: Iterable[str]) -> Dict[str, LiveStream]:
        login_list = [login.lower() for login in logins]
        if not login_list:
            return {}

        token = self._get_token()
        params: List[Tuple[str, str]] = [("user_login", login) for login in login_list]
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {token}",
        }

        response = requests.get(TWITCH_STREAMS_URL, params=params, headers=headers, timeout=20)
        if response.status_code == 401:
            # Token may have been revoked/expired early. Refresh once and retry.
            log("Twitch token rejected, refreshing token")
            self._access_token = None
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(TWITCH_STREAMS_URL, params=params, headers=headers, timeout=20)

        response.raise_for_status()
        data = response.json().get("data", [])

        live: Dict[str, LiveStream] = {}
        for item in data:
            login = str(item.get("user_login", "")).lower()
            tags = item.get("tags") or []
            live[login] = LiveStream(
                login=login,
                display_name=item.get("user_name") or login,
                title=item.get("title") or "Live Stream",
                category=item.get("game_name") or "Live",
                tags=[str(tag) for tag in tags],
                viewer_count=item.get("viewer_count"),
            )
        return live


class BridgeProcess:
    def __init__(self) -> None:
        self.streamlink_proc: Optional[subprocess.Popen] = None
        self.ffmpeg_proc: Optional[subprocess.Popen] = None
        self.current_login: Optional[str] = None

    def running(self) -> bool:
        if not self.ffmpeg_proc:
            return False
        return self.ffmpeg_proc.poll() is None

    def stop(self) -> None:
        if not self.streamlink_proc and not self.ffmpeg_proc:
            return

        log("Stopping current Twitch → AzuraCast bridge")
        for proc in [self.ffmpeg_proc, self.streamlink_proc]:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        deadline = time.time() + 10
        while time.time() < deadline:
            all_done = True
            for proc in [self.ffmpeg_proc, self.streamlink_proc]:
                if proc and proc.poll() is None:
                    all_done = False
            if all_done:
                break
            time.sleep(0.25)

        for proc in [self.ffmpeg_proc, self.streamlink_proc]:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

        self.streamlink_proc = None
        self.ffmpeg_proc = None
        self.current_login = None

    def start(self, stream: LiveStream, channel_cfg: ChannelConfig, settings: Dict[str, str]) -> None:
        self.stop()

        host = settings["az_host"]
        port = settings["az_port"]
        mount = settings["az_mount"]
        bitrate = settings["bitrate"]
        quality = settings["quality"]
        public = settings["icecast_public"]
        audio_format = settings["audio_format"].lower()
        sample_rate = settings["sample_rate"]
        channels = settings["channels"]
        metadata = format_metadata(stream, settings["metadata_template"])

        if audio_format != "mp3":
            raise RuntimeError("Only mp3 output is currently supported by this starter project.")

        user = quote(channel_cfg.azuracast_user, safe="")
        password = quote(channel_cfg.azuracast_password, safe="")
        mount_escaped = quote(mount.lstrip("/"), safe="/")
        icecast_url = f"icecast://{user}:{password}@{host}:{port}/{mount_escaped}"

        twitch_url = f"https://www.twitch.tv/{stream.login}"

        streamlink_cmd = [
            "streamlink",
            "--stdout",
            "--twitch-disable-ads",
            "--retry-streams",
            "10",
            twitch_url,
            quality,
        ]

        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            settings["ffmpeg_loglevel"],
            "-re",
            "-i",
            "pipe:0",
            "-vn",
            "-ac",
            channels,
            "-ar",
            sample_rate,
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            "-content_type",
            "audio/mpeg",
            "-ice_name",
            metadata,
            "-ice_description",
            metadata,
            "-ice_genre",
            stream.category,
            "-ice_public",
            public,
            "-metadata",
            f"artist={stream.display_name}",
            "-metadata",
            f"title={metadata}",
            "-f",
            "mp3",
            icecast_url,
        ]

        log(f"Starting live bridge: {metadata}")
        log(f"Using AzuraCast streamer username: {channel_cfg.azuracast_user}")

        self.streamlink_proc = subprocess.Popen(
            streamlink_cmd,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            stdin=subprocess.DEVNULL,
        )

        if self.streamlink_proc.stdout is None:
            raise RuntimeError("Streamlink did not provide stdout pipe")

        self.ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=self.streamlink_proc.stdout,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        # Let ffmpeg own the pipe; this allows streamlink to get SIGPIPE if ffmpeg exits.
        self.streamlink_proc.stdout.close()
        self.current_login = stream.login


def format_metadata(stream: LiveStream, template: str) -> str:
    tags = ", ".join(stream.tags)
    metadata = template.format(
        login=stream.login,
        display_name=stream.display_name,
        title=stream.title,
        category=stream.category,
        tags=tags,
    )
    # Keep metadata compact and avoid line breaks that can confuse Icecast clients.
    metadata = re.sub(r"\s+", " ", metadata).strip()
    max_len = int(env("METADATA_MAX_LENGTH", "180"))
    if len(metadata) > max_len:
        metadata = metadata[: max_len - 1].rstrip() + "…"
    return metadata


def load_config() -> Tuple[List[ChannelConfig], Dict[str, str]]:
    priority = split_csv(env("TWITCH_PRIORITY", required=True))
    if not priority:
        raise RuntimeError("TWITCH_PRIORITY must include at least one Twitch channel")

    channel_configs: List[ChannelConfig] = []
    for login in priority:
        key = channel_env_key(login)
        user = env(f"AZURACAST_USER_{key}", required=True)
        password = env(f"AZURACAST_PASSWORD_{key}", required=True)
        if login != login.lower():
            raise RuntimeError(f"Twitch channel must be lowercase in TWITCH_PRIORITY: {login}")
        if user != user.lower():
            raise RuntimeError(f"AzuraCast username should be lowercase for {login}: {user}")
        channel_configs.append(ChannelConfig(login, user, password))

    settings = {
        "az_host": env("AZURACAST_HOST", "192.168.1.17"),
        "az_port": env("AZURACAST_PORT", "8005"),
        "az_mount": normalize_mount(env("AZURACAST_MOUNT", "/radio.mp3")),
        "bitrate": env("AZURACAST_BITRATE", "192k"),
        "audio_format": env("AZURACAST_FORMAT", "mp3"),
        "sample_rate": env("AUDIO_SAMPLE_RATE", "44100"),
        "channels": env("AUDIO_CHANNELS", "2"),
        "quality": env("TWITCH_QUALITY", "best"),
        "icecast_public": "1" if parse_bool(env("AZURACAST_ICECAST_PUBLIC", "0")) else "0",
        "metadata_template": env(
            "METADATA_TEMPLATE",
            "{display_name} is On Twitch Live - {category} - {title}",
        ),
        "ffmpeg_loglevel": env("FFMPEG_LOGLEVEL", "warning"),
    }
    return channel_configs, settings


def main() -> int:
    log(f"Starting {APP_NAME}")

    client_id = env("TWITCH_CLIENT_ID", required=True)
    client_secret = env("TWITCH_CLIENT_SECRET", required=True)
    poll_seconds = int(env("TWITCH_POLL_SECONDS", "30"))
    switch_on_higher_priority = parse_bool(env("SWITCH_TO_HIGHER_PRIORITY_WHILE_LIVE", "1"), True)
    stop_when_offline = parse_bool(env("STOP_WHEN_SELECTED_CHANNEL_OFFLINE", "1"), True)

    channel_configs, settings = load_config()
    channel_by_login = {cfg.twitch_login: cfg for cfg in channel_configs}
    priority_logins = [cfg.twitch_login for cfg in channel_configs]

    log("Priority order: " + " > ".join(priority_logins))
    log(f"AzuraCast target: {settings['az_host']}:{settings['az_port']}{settings['az_mount']}")

    twitch = TwitchClient(client_id, client_secret)
    bridge = BridgeProcess()
    shutdown = False

    def handle_signal(signum, frame):  # noqa: ANN001
        nonlocal shutdown
        log(f"Received signal {signum}, shutting down")
        shutdown = True
        bridge.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not shutdown:
        try:
            live_map = twitch.get_live_streams(priority_logins)
            selected: Optional[LiveStream] = None
            for login in priority_logins:
                if login in live_map:
                    selected = live_map[login]
                    break

            if selected:
                if bridge.running():
                    if bridge.current_login == selected.login:
                        log(f"Still live: {selected.display_name}")
                    elif switch_on_higher_priority:
                        bridge.start(selected, channel_by_login[selected.login], settings)
                    else:
                        log(
                            f"{selected.display_name} is live, but keeping current stream: "
                            f"{bridge.current_login}"
                        )
                else:
                    bridge.start(selected, channel_by_login[selected.login], settings)
            else:
                if bridge.running() and stop_when_offline:
                    log("No priority Twitch channels are live. Disconnecting so AzuraCast can fall back to AutoDJ.")
                    bridge.stop()
                else:
                    log("No priority Twitch channels are live")

            # If streamlink/ffmpeg died, clean up so next loop can retry if still live.
            if bridge.ffmpeg_proc and bridge.ffmpeg_proc.poll() is not None:
                log(f"FFmpeg exited with code {bridge.ffmpeg_proc.returncode}")
                bridge.stop()
            if bridge.streamlink_proc and bridge.streamlink_proc.poll() is not None:
                log(f"Streamlink exited with code {bridge.streamlink_proc.returncode}")
                bridge.stop()

        except Exception as exc:
            log(f"ERROR: {exc}")
            bridge.stop()

        for _ in range(max(1, poll_seconds)):
            if shutdown:
                break
            time.sleep(1)

    bridge.stop()
    log("Exited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
