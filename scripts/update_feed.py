#!/usr/bin/env python3
"""Build an AltStore source from public, completed main-branch IPA releases."""

import json
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "apps.json"
RELEASE_LIMIT = 20
REPOSITORIES = [
    {
        "repo": "NullSign",
        "name": "NullSign",
        "bundle": "com.elmat.NullSign",
        "subtitle": "Sign and install iOS apps",
        "description": "A local iOS IPA signer and installer.",
        "icon": "https://raw.githubusercontent.com/nulldev85/NullSign/main/Feather/Resources/Assets.xcassets/NullSignBlue.appiconset/nullsign.png",
        "tint": "#148BF4",
        "category": "utilities",
        "asset": "NullSign-unsigned.ipa",
    },
    {
        "repo": "NullSports",
        "name": "Lineup",
        "bundle": "com.nulldev85.NullSports.iOS",
        "subtitle": "Live TV, sports, and your media library",
        "description": "Live television, sports, and library playback in one app. Inspired by Janky and Stadium-Sync. Shoutout to Hippo and Streamers86.",
        "icon": "https://raw.githubusercontent.com/nulldev85/NullSports/main/iPhone/Assets.xcassets/LineupAppIcon.appiconset/LineupAppIcon.png",
        "tint": "#168CFF",
        "category": "entertainment",
        "asset": "Lineup.ipa",
    },
    {
        "repo": "Aether",
        "name": "Aether",
        "bundle": "com.example.IPTVRadio",
        "subtitle": "IPTV Radio",
        "description": "A radio-only streaming app for IPTV audio channels. Inspired by Orbitrr. Shoutout to Keeb.",
        "icon": "https://raw.githubusercontent.com/nulldev85/Aether/main/IPTVRadio/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
        "tint": "#5277E8",
        "category": "entertainment",
        "asset": "IPTVRadio-unsigned-device.ipa",
    },
]


def request_json(url: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "nulldev85-app-source-feed",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def release_metadata(body: str) -> dict[str, str]:
    values = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key.startswith("Source-"):
            values[key] = value.strip()
    return values


def app_versions(app: dict) -> list[dict]:
    url = f"https://api.github.com/repos/nulldev85/{app['repo']}/releases?per_page=100"
    releases = request_json(url)
    versions = []
    for release in releases:
        if release.get("draft") or release.get("prerelease"):
            continue
        if not release.get("tag_name", "").startswith("source-"):
            continue
        metadata = release_metadata(release.get("body") or "")
        required = (
            "Source-App",
            "Source-Bundle-Identifier",
            "Source-Version",
            "Source-Build-Version",
            "Source-Branch",
            "Source-SHA",
        )
        if any(not metadata.get(key) for key in required):
            continue
        if metadata["Source-App"] != app["name"] or metadata["Source-Branch"] != "main":
            continue
        if metadata["Source-Bundle-Identifier"] != app["bundle"]:
            continue
        asset = next(
            (item for item in release.get("assets", []) if item.get("name") == app["asset"]),
            None,
        )
        if not asset or not asset.get("browser_download_url") or not asset.get("size"):
            continue
        published = release.get("published_at")
        if not published:
            continue
        sha = metadata["Source-SHA"]
        version = {
            "version": metadata["Source-Version"],
            "buildVersion": metadata["Source-Build-Version"],
            "date": published,
            "localizedDescription": f"Unsigned IPA from successful main build {sha[:7]}. Sign before installing.",
            "downloadURL": asset["browser_download_url"],
            "size": asset["size"],
        }
        minimum_os = metadata.get("Source-Minimum-OS-Version")
        if minimum_os and minimum_os != "unknown":
            version["minOSVersion"] = minimum_os
        versions.append((published, version))
    versions.sort(key=lambda item: item[0], reverse=True)
    return [version for _, version in versions[:RELEASE_LIMIT]]


def main() -> None:
    current = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    apps = []
    for config in REPOSITORIES:
        versions = app_versions(config)
        print(f"{config['name']}: {len(versions)} published main build(s)")
        if not versions:
            continue
        apps.append(
            {
                "name": config["name"],
                "bundleIdentifier": config["bundle"],
                "developerName": "NullDev85",
                "subtitle": config["subtitle"],
                "localizedDescription": config["description"],
                "iconURL": config["icon"],
                "tintColor": config["tint"],
                "category": config["category"],
                "versions": versions,
            }
        )
    current["apps"] = apps
    current["featuredApps"] = [app["bundleIdentifier"] for app in apps]
    FEED_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(apps)} app entries from completed main-branch releases.")


if __name__ == "__main__":
    main()
