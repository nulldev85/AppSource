#!/usr/bin/env python3
"""Post clean release embeds to Discord when new builds land in apps.json."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

USER_AGENT = "nulldev85-app-source-discord/1.0"
WEBHOOK_PATTERN = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]+(?:\?.*)?$")

APP_PRESENTATION: dict[str, dict[str, Any]] = {
    "com.nulldev85.NullSports.iOS": {
        "platform": "iPhone",
        "color": 0xFF3B4E,
        "url": "https://nulldev85.github.io/#lineup",
    },
    "com.nulldev85.NullSports": {
        "platform": "Apple TV",
        "color": 0xFF3B4E,
        "url": "https://nulldev85.github.io/#lineup",
    },
    "com.elmat.NullSign": {
        "platform": "iOS",
        "color": 0x1C9BFF,
        "url": "https://nulldev85.github.io/#nullsign",
    },
}


def parse_iso_date(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_by_bundle(feed: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    result: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for app in feed.get("apps") or []:
        bundle = app.get("bundleIdentifier")
        versions = app.get("versions") or []
        if bundle and versions:
            result[bundle] = (app, versions[0])
    return result


def new_releases(previous_feed: dict[str, Any], current_feed: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return apps whose newest build is genuinely newer than previous_feed."""
    previous = latest_by_bundle(previous_feed)
    announced: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for app in current_feed.get("apps") or []:
        bundle = app.get("bundleIdentifier")
        versions = app.get("versions") or []
        if not bundle or not versions:
            continue
        latest = versions[0]
        latest_key = (latest.get("version"), latest.get("buildVersion"))
        if not latest_key[0] or not latest_key[1]:
            continue
        prev_entry = previous.get(bundle)
        if prev_entry is not None:
            prev_latest = prev_entry[1]
            prev_key = (prev_latest.get("version"), prev_latest.get("buildVersion"))
            if latest_key == prev_key:
                continue
            prev_date = parse_iso_date(prev_latest.get("date"))
            curr_date = parse_iso_date(latest.get("date"))
            if prev_date and curr_date and curr_date < prev_date:
                continue
        announced.append((app, latest))
    return announced


def format_size(size_bytes: Any) -> str | None:
    if not isinstance(size_bytes, (int, float)) or size_bytes <= 0:
        return None
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def build_payload(
    app: dict[str, Any],
    release: dict[str, Any],
    role_id: str = "",
) -> dict[str, Any]:
    bundle = app.get("bundleIdentifier", "")
    style = APP_PRESENTATION.get(
        bundle,
        {"platform": "Apple", "color": 0xE4E4E7, "url": "https://nulldev85.github.io"},
    )
    name = app.get("name", bundle)
    version = release.get("version", "")
    build = release.get("buildVersion", "")
    notes = (release.get("localizedDescription") or "").strip()
    if len(notes) > 3500:
        notes = notes[:3497].rstrip() + "..."

    fields = [
        {"name": "Platform", "value": style["platform"], "inline": True},
        {"name": "Build", "value": f"`{version} ({build})`", "inline": True},
    ]
    size_label = format_size(release.get("size"))
    if size_label:
        fields.append({"name": "Size", "value": size_label, "inline": True})
    fields.append(
        {
            "name": "Get It",
            "value": f"Update in **NullSign** or grab the IPA at [nulldev85.github.io]({style['url']})",
            "inline": False,
        }
    )

    embed: dict[str, Any] = {
        "title": f"{name} {version} ({build})",
        "url": style["url"],
        "description": notes or "New build available.",
        "color": style["color"],
        "fields": fields,
        "footer": {"text": "Null's Apps"},
    }
    if release.get("date"):
        embed["timestamp"] = release["date"]
    if app.get("iconURL"):
        embed["thumbnail"] = {"url": app["iconURL"]}

    payload: dict[str, Any] = {
        "username": "Null's Apps Releases",
        "embeds": [embed],
    }
    clean_role = role_id.strip()
    if clean_role.isdigit():
        payload["content"] = f"<@&{clean_role}>"
        payload["allowed_mentions"] = {"parse": [], "roles": [clean_role]}
    else:
        payload["allowed_mentions"] = {"parse": []}
    return payload


def load_json_source(spec: str) -> dict[str, Any]:
    path = Path(spec)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if ":" in spec:
        raw = subprocess.check_output(["git", "show", spec], text=True, encoding="utf-8")
        return json.loads(raw)
    raise FileNotFoundError(f"Could not load feed from {spec}")


def post_webhook(url: str, payload: dict[str, Any]) -> None:
    if not WEBHOOK_PATTERN.match(url):
        raise ValueError("Invalid Discord webhook URL.")
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    for attempt in range(3):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
                return
        except urllib.error.HTTPError as err:
            if err.code == 429 and attempt < 2:
                retry = 2.0
                try:
                    retry = float(json.loads(err.read().decode("utf-8")).get("retry_after", retry))
                except Exception:
                    pass
                time.sleep(max(0.5, retry) + 0.25)
                continue
            if err.code in (500, 502, 503, 504) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Announce newly published AppSource builds in Discord.")
    parser.add_argument("--previous", required=True, help="Path or git ref:path for the previous apps.json.")
    parser.add_argument("--current", required=True, help="Path to the updated apps.json.")
    args = parser.parse_args()

    webhook_url = os.environ.get("DISCORD_RELEASES_WEBHOOK_URL", "").strip()
    if not webhook_url:
        print("Discord webhook not configured; skipping release notification.")
        return 0

    role_id = os.environ.get("DISCORD_RELEASES_ROLE_ID", "").strip()
    previous_feed = load_json_source(args.previous)
    current_feed = load_json_source(args.current)
    releases = new_releases(previous_feed, current_feed)
    if not releases:
        print("No new builds to announce in Discord.")
        return 0

    for app, release in releases:
        payload = build_payload(app, release, role_id=role_id)
        try:
            post_webhook(webhook_url, payload)
            print(f"Announced {app.get('name')} {release.get('version')} ({release.get('buildVersion')}) in Discord.")
        except Exception as exc:
            # Fail open so a transient Discord outage never fails the feed publisher.
            print(f"::warning::Discord release notification failed for {app.get('name')}: {exc}")
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
