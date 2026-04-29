#!/usr/bin/env python3
"""
Twitch -> AzuraCast/Icecast live bridge.

Polls priority Twitch channels, selects the first live channel, pipes audio from
Streamlink into ffmpeg, and sends it to AzuraCast as a live DJ source.

This version supports AzuraCast's default Streamer/DJ mount of "/" without
requiring an AzuraCast change. For root mounts, it uses FFmpeg's HTTP PUT output
instead of FFmpeg's icecast:// protocol, because the icecast protocol refuses a
plain root mount and throws: "No mountpoint (path) specified!".
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests


def log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    raw = env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        log(f"Invalid integer for {name}={raw!r}; using {default}")
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = env(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "y", "on"}


def normalize_username(username: str) -> str:
    return username.strip().lower()


def env_key_for_username(username: str) -> str:
    # jimboslicechicago -> JIMBOSLICECHICAGO
    # chuck-the-dj -> CHUCK_THE_DJ
    return re.sub(r"[^A-Z0-9]+", "_", username.upper()).strip("_")


def parse_usernames() -> list[str]:
    users = [normalize_username(u) for u in env("TWITCH_USERNAMES").split(",") if u.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for user in users:
        if user and user not in seen:
            ordered.append(user)
            seen.add(user)
    return ordered


def require_config() -> None:
    missing = []
    for name in ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET", "AZURACAST_HOST", "AZURACAST_PORT"):
        if not env(name):
            missing.append(name)
    if not parse_usernames():
        missing.append("TWITCH_USERNAMES")
    if missing:
        raise SystemExit("Missing required config: " + ", ".join(missing))


def azuracast_streamer_username(twitch_username: str) -> str:
    key = env_key_for_username(twitch_username)
    return normalize_username(env(f"AZURACAST_STREAMER_{key}_USERNAME", twitch_username))


def azuracast_streamer_password(twitch_username: str) -> str:
    key = env_key_for_username(twitch_username)
    password = env(f"AZURACAST_STREAMER_{key}_PASSWORD")
    if not password:
        raise RuntimeError(f"Missing AZURACAST_STREAMER_{key}_PASSWORD for {twitch_username}")
    return password


def azuracast_mount() -> str:
    # User does not want to change AzuraCast. Default to the mount AzuraCast shows: /
    mount = env("AZURACAST_MOUNT", "/") or "/"
    if not mount.startswith("/"):
        mount = "/" + mount
    return mount


def azuracast_auth(twitch_username: str) -> tuple[str, str]:
    """
    Build the source login credentials.

    Default auth mode is source_password because AzuraCast's Icecast DJ panel
    commonly shows the password as: dj_username:dj_password.

    Supported modes:
      source_password  -> user=source, password=dj_username:dj_password
      streamer_login   -> user=dj_username, password=dj_password
    """
    auth_mode = env("AZURACAST_AUTH_MODE", "source_password").lower()
    streamer_user = azuracast_streamer_username(twitch_username)
    streamer_pass = azuracast_streamer_password(twitch_username)

    if auth_mode == "streamer_login":
        return streamer_user, streamer_pass

    sep = env("AZURACAST_SOURCE_PASSWORD_SEPARATOR", ":") or ":"
    source_user = env("AZURACAST_SOURCE_USER", "source") or "source"
    return source_user, f"{streamer_user}{sep}{streamer_pass}"


def azuracast_output_mode() -> str:
    """
    auto:
      - root mount / uses HTTP PUT to avoid ffmpeg icecast:// root-mount failure
      - non-root mounts use icecast://
    http_put:
      - always use HTTP PUT
    icecast:
      - always use icecast://
    """
    requested = env("AZURACAST_OUTPUT_MODE", "auto").lower()
    if requested not in {"auto", "http_put", "icecast"}:
        log(f"Invalid AZURACAST_OUTPUT_MODE={requested!r}; using auto")
        requested = "auto"

    if requested == "auto":
        return "http_put" if azuracast_mount() == "/" else "icecast"
    return requested


def azuracast_output_url(twitch_username: str) -> str:
    host = env("AZURACAST_HOST", "192.168.1.17")
    port = env("AZURACAST_PORT", "8005")
    mount = azuracast_mount()
    user, password = azuracast_auth(twitch_username)

    scheme = "http" if azuracast_output_mode() == "http_put" else "icecast"
    return f"{scheme}://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}{mount}"


def safe_ice_header(value: str, max_len: int = 255) -> str:
    # Prevent accidental header injection and keep Icecast metadata tidy.
    return value.replace("\r", " ").replace("\n", " ").strip()[:max_len]


@dataclass
class SelectedStream:
    twitch_username: str
    display_name: str
    stream_id: str
    title: str
    category: str
    viewer_count: int
    started_at: str

    @property
    def metadata_name(self) -> str:
        category = self.category or "Twitch"
        title = self.title or "Live"
        return f"{self.display_name} is On Twitch Live - {category} - {title}"


class TwitchClient:
    def __init__(self) -> None:
        self.client_id = env("TWITCH_CLIENT_ID")
        self.client_secret = env("TWITCH_CLIENT_SECRET")
        self.access_token: Optional[str] = None
        self.token_expiry_epoch = 0.0

    def get_app_access_token(self) -> str:
        now = time.time()
        if self.access_token and now < self.token_expiry_epoch - 300:
            return self.access_token

        log("Refreshing Twitch app access token")
        response = requests.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        self.access_token = data["access_token"]
        self.token_expiry_epoch = now + int(data.get("expires_in", 3600))
        return self.access_token

    def headers(self) -> dict[str, str]:
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.get_app_access_token()}",
        }

    def get_live_streams(self, usernames: list[str]) -> dict[str, SelectedStream]:
        if not usernames:
            return {}

        params: list[tuple[str, str]] = [("user_login", user) for user in usernames[:100]]
        response = requests.get(
            "https://api.twitch.tv/helix/streams",
            headers=self.headers(),
            params=params,
            timeout=20,
        )

        if response.status_code == 401:
            self.access_token = None
            response = requests.get(
                "https://api.twitch.tv/helix/streams",
                headers=self.headers(),
                params=params,
                timeout=20,
            )

        if response.status_code == 429:
            retry_after = response.headers.get("Ratelimit-Reset")
            raise RuntimeError(f"Twitch rate limited this bridge. Retry after/reset: {retry_after or 'unknown'}")

        response.raise_for_status()
        data = response.json().get("data", [])

        live: dict[str, SelectedStream] = {}
        for item in data:
            login = normalize_username(item.get("user_login", ""))
            if not login:
                continue
            live[login] = SelectedStream(
                twitch_username=login,
                display_name=item.get("user_name") or login,
                stream_id=item.get("id") or "",
                title=item.get("title") or "Live",
                category=item.get("game_name") or "Twitch",
                viewer_count=int(item.get("viewer_count") or 0),
                started_at=item.get("started_at") or "",
            )
        return live


class BridgeProcess:
    def __init__(self, selected: SelectedStream) -> None:
        self.selected = selected
        self.started_epoch = time.time()
        self.streamlink_proc: Optional[subprocess.Popen[bytes]] = None
        self.ffmpeg_proc: Optional[subprocess.Popen[bytes]] = None

    def start(self) -> None:
        stream_url = f"https://www.twitch.tv/{self.selected.twitch_username}"
        quality = env("STREAMLINK_QUALITY", "audio_only") or "audio_only"
        streamlink_loglevel = env("STREAMLINK_LOGLEVEL", "info") or "info"
        ffmpeg_loglevel = env("FFMPEG_LOGLEVEL", "warning") or "warning"
        audio_bitrate = env("AUDIO_BITRATE", "128k") or "128k"
        audio_sample_rate = env("AUDIO_SAMPLE_RATE", "44100") or "44100"
        output_url = azuracast_output_url(self.selected.twitch_username)
        output_mode = azuracast_output_mode()

        log(f"Starting live bridge: {self.selected.metadata_name}")
        log(f"Using AzuraCast streamer username: {azuracast_streamer_username(self.selected.twitch_username)}")
        log(f"Using AzuraCast target: {env('AZURACAST_HOST', '192.168.1.17')}:{env('AZURACAST_PORT', '8005')}{azuracast_mount()}")
        log(f"Using AzuraCast output mode: {output_mode}")

        streamlink_cmd = [
            "streamlink",
            "--loglevel",
            streamlink_loglevel,
            "--stdout",
            stream_url,
            quality,
        ]

        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            ffmpeg_loglevel,
            "-i",
            "pipe:0",
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            audio_bitrate,
            "-ar",
            audio_sample_rate,
            "-ac",
            "2",
            "-content_type",
            "audio/mpeg",
        ]

        if output_mode == "http_put":
            headers = (
                f"Ice-Name: {safe_ice_header(self.selected.metadata_name)}\r\n"
                f"Ice-Genre: {safe_ice_header(self.selected.category or 'Twitch')}\r\n"
                f"Ice-Description: {safe_ice_header(f'Twitch live relay for {self.selected.display_name}')}\r\n"
            )
            ffmpeg_cmd.extend([
                "-method",
                "PUT",
                "-headers",
                headers,
            ])
        else:
            ffmpeg_cmd.extend([
                "-ice_name",
                safe_ice_header(self.selected.metadata_name),
                "-ice_genre",
                safe_ice_header(self.selected.category or "Twitch"),
                "-ice_description",
                safe_ice_header(f"Twitch live relay for {self.selected.display_name}"),
            ])

        ffmpeg_cmd.extend([
            "-f",
            "mp3",
            output_url,
        ])

        # New process groups let us stop both child processes cleanly.
        self.streamlink_proc = subprocess.Popen(
            streamlink_cmd,
            stdout=subprocess.PIPE,
            stderr=None,
            preexec_fn=os.setsid,
        )

        assert self.streamlink_proc.stdout is not None
        self.ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=self.streamlink_proc.stdout,
            stderr=None,
            preexec_fn=os.setsid,
        )
        self.streamlink_proc.stdout.close()

    def is_running(self) -> bool:
        return bool(
            self.streamlink_proc
            and self.ffmpeg_proc
            and self.streamlink_proc.poll() is None
            and self.ffmpeg_proc.poll() is None
        )

    def stopped_quickly(self) -> bool:
        return time.time() - self.started_epoch < 20

    def stop(self) -> None:
        log("Stopping current Twitch → AzuraCast bridge")
        for proc in (self.ffmpeg_proc, self.streamlink_proc):
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
        time.sleep(2)
        for proc in (self.ffmpeg_proc, self.streamlink_proc):
            if proc and proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass


def choose_priority_stream(priority_usernames: list[str], live: dict[str, SelectedStream]) -> Optional[SelectedStream]:
    for username in priority_usernames:
        if username in live:
            return live[username]
    return None


def stream_identity(selected: SelectedStream) -> str:
    if env_bool("RESTART_ON_METADATA_CHANGE", False):
        return f"{selected.twitch_username}|{selected.stream_id}|{selected.title}|{selected.category}"
    return f"{selected.twitch_username}|{selected.stream_id}"


def main() -> int:
    require_config()

    priority_usernames = parse_usernames()
    poll_seconds = env_int("TWITCH_POLL_SECONDS", 30)
    backoff_seconds = env_int("BRIDGE_BACKOFF_SECONDS", 120)
    twitch = TwitchClient()

    log("Twitch → AzuraCast bridge starting")
    log(f"Priority order: {', '.join(priority_usernames)}")
    log(f"Polling Twitch every {poll_seconds} seconds")
    log(f"AzuraCast target: {env('AZURACAST_HOST', '192.168.1.17')}:{env('AZURACAST_PORT', '8005')}{azuracast_mount()}")
    log(f"AzuraCast output mode: {azuracast_output_mode()}")

    current: Optional[BridgeProcess] = None
    current_identity: Optional[str] = None
    backoff_until = 0.0

    while True:
        try:
            if current and not current.is_running():
                log("Current bridge process ended")
                quick = current.stopped_quickly()
                current.stop()
                current = None
                current_identity = None
                if quick:
                    backoff_until = time.time() + backoff_seconds
                    log(f"Bridge stopped quickly; backing off for {backoff_seconds} seconds")

            if time.time() < backoff_until:
                time.sleep(min(10, max(1, int(backoff_until - time.time()))))
                continue

            live = twitch.get_live_streams(priority_usernames)
            selected = choose_priority_stream(priority_usernames, live)

            if not selected:
                if current:
                    current.stop()
                    current = None
                    current_identity = None
                log("No priority Twitch channels are live")
                time.sleep(poll_seconds)
                continue

            desired_identity = stream_identity(selected)
            if not current or current_identity != desired_identity:
                if current:
                    current.stop()
                current = BridgeProcess(selected)
                current.start()
                current_identity = desired_identity
            else:
                log(f"Already bridging priority channel: {selected.display_name}")

            time.sleep(poll_seconds)

        except KeyboardInterrupt:
            if current:
                current.stop()
            log("Bridge stopped")
            return 0
        except Exception as exc:
            log(f"ERROR: {exc}")
            if current:
                current.stop()
                current = None
                current_identity = None
            time.sleep(backoff_seconds)


if __name__ == "__main__":
    sys.exit(main())
