#!/usr/bin/env python3
"""Mirror successful main-branch source IPAs into this public distribution repo."""

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "apps.json"
ICON_DIR = ROOT / "icons"
# The source's own icon lives only here; the site's fonts/icon.py draws it.
SOURCE_ICON = "source.png"
NOTES_PATH = ROOT / "release-notes.json"
OWNER = "nulldev85"
DIST_REPO = os.environ.get("GITHUB_REPOSITORY", f"{OWNER}/AppSource")
RELEASE_LIMIT = 20
API_ROOT = "https://api.github.com"
REPOSITORIES = [
    {
        "repo": "NullSign",
        "name": "NullSign",
        "bundle": "com.elmat.NullSign",
        "private": True,
        "subtitle": "Sign and install iOS apps",
        "description": "A local iOS IPA signer and installer.",
        "iconPath": "Feather/Resources/Assets.xcassets/NullSignBlue.appiconset/nullsign.png",
        "iconFile": "nullsign.png",
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
        "iconPath": "iPhone/Assets.xcassets/LineupAppIcon.appiconset/LineupAppIcon.png",
        "iconFile": "lineup.png",
        "tint": "#168CFF",
        "category": "entertainment",
        "asset": "Lineup-iPhone-unsigned.ipa",
    },
    {
        "repo": "NullSports",
        "name": "Lineup tvOS",
        "bundle": "com.nulldev85.NullSports",
        "subtitle": "Live television, sports, and your media library on Apple TV",
        "description": "Live television, sports, and library playback on Apple TV. Inspired by Janky and Stadium-Sync. Shoutout to Hippo and Streamers86.",
        "iconPath": "iPhone/Assets.xcassets/LineupAppIcon.appiconset/LineupAppIcon.png",
        "iconFile": "lineup.png",
        "tint": "#168CFF",
        "category": "entertainment",
        "asset": "Lineup-tvOS-unsigned.ipa",
    },
    {
        "repo": "Aether",
        "private": True,
        "name": "Aether",
        "bundle": "com.example.IPTVRadio",
        "subtitle": "IPTV Radio",
        "description": "A radio-only streaming app for IPTV audio channels. Inspired by Orbitrr. Shoutout to Keeb.",
        "iconPath": "IPTVRadio/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
        "iconFile": "aether.png",
        "tint": "#5277E8",
        "category": "entertainment",
        "asset": "IPTVRadio-unsigned-device.ipa",
    },
]


class SourceReleaseUnavailable(RuntimeError):
    """A source repo has no eligible release visible to this feed run."""


class ReleaseNotesUnavailable(SourceReleaseUnavailable):
    """A build is valid, but its user-facing changes have not been written."""


def checked_notes(notes) -> list[str]:
    if not isinstance(notes, list) or not 1 <= len(notes) <= 12:
        raise ValueError("Release notes need between one and twelve short bullets.")
    result = []
    for note in notes:
        if not isinstance(note, str) or not 12 <= len(note.strip()) <= 600:
            raise ValueError("Each release note must be a short, readable sentence.")
        note = note.strip()
        if re.search(r"[\r\n]|Source-[A-Za-z-]+:|Traceback \(|(?:fatal )?error:|xcodebuild|being prepared", note, re.I):
            raise ValueError("Build metadata, compiler output and placeholders are not release notes.")
        result.append(note)
    return result


def release_note_catalog() -> list[dict]:
    catalog = json.loads(NOTES_PATH.read_text(encoding="utf-8"))
    if catalog.get("schemaVersion") != 1 or not isinstance(catalog.get("releases"), list):
        raise ValueError("Unsupported release-note catalog.")
    seen = set()
    for record in catalog["releases"]:
        checked_notes(record.get("notes"))
        if not all(isinstance(record.get(field), str) and record[field] for field in ("bundleIdentifier", "version", "buildVersion")):
            raise ValueError("Release notes must identify their app, version and build.")
        if not isinstance(record.get("sourceSHAs"), list) or not record["sourceSHAs"]:
            raise ValueError("Release notes must name the exact source commit.")
        for sha in record["sourceSHAs"]:
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("Release-note source commits must be full Git SHAs.")
            key = (record["bundleIdentifier"], record["version"], record["buildVersion"], sha)
            if key in seen:
                raise ValueError("Conflicting release notes for the same build and commit.")
            seen.add(key)
    return catalog["releases"]


def human_release_notes(app: dict, source_release: dict, metadata: dict) -> list[str]:
    for record in release_note_catalog():
        if (record["bundleIdentifier"] == app["bundle"]
                and record["version"] == metadata["Source-Version"]
                and record["buildVersion"] == metadata["Source-Build-Version"]
                and metadata["Source-SHA"] in record["sourceSHAs"]):
            return checked_notes(record["notes"])
    # Future source releases can carry explicitly written notes themselves.
    # Never turn commit titles, CI diagnostics or the Source-* block into copy.
    body = source_release.get("body") or ""
    heading = re.search(r"(?im)^#{1,3}\s+(?:what['’]s new|release notes)\s*$", body)
    if heading:
        section = re.split(r"(?m)^#{1,3}\s+", body[heading.end():], maxsplit=1)[0]
        notes = [re.sub(r"^\s*[-*•]\s+", "", line).strip()
                 for line in section.splitlines() if re.match(r"^\s*[-*•]\s+", line)]
        try:
            return checked_notes(notes)
        except ValueError:
            pass
    raise ReleaseNotesUnavailable(
        f"Write release notes for {app['name']} {metadata['Source-Version']} "
        f"build {metadata['Source-Build-Version']} ({metadata['Source-SHA'][:7]}) "
        "in release-notes.json or the source release's What's new section."
    )


def distribution_notes(app: dict, source_release: dict, metadata: dict, notes: list[str]) -> str:
    public_notes = "\n".join(f"- {note}" for note in checked_notes(notes))
    details = [f"Source-{field}: {metadata['Source-' + field]}" for field in
               ("App", "Bundle-Identifier", "Version", "Build-Version", "Branch", "SHA")]
    details.insert(4, f"Source-Minimum-OS-Version: {metadata.get('Source-Minimum-OS-Version', 'unknown')}")
    details += [f"Source-Origin-Repository: {OWNER}/{app['repo']}",
                f"Source-Origin-Tag: {source_release['tag_name']}"]
    return ("## What's new\n\n" + public_notes
            + "\n\nSign this IPA with your preferred signer before installing."
            + "\n\n## Build details\n\n" + "\n".join(details) + "\n")


def request(
    url: str,
    *,
    token: str = "",
    accept: str = "application/vnd.github+json",
    content_type: str = "",
    data=None,
    method=None,
):
    headers = {
        "Accept": accept,
        "User-Agent": "nulldev85-app-source-feed",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    elif data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def request_json(url: str, *, token: str = "", data=None, method=None) -> dict | list:
    body = request(url, token=token, data=data, method=method)
    return json.loads(body.decode("utf-8"))


def maybe_json(url: str, *, token: str) -> dict | None:
    try:
        return request_json(url, token=token)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def source_token() -> str:
    return os.environ.get("SOURCE_REPOS_TOKEN", "")


def distribution_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("APP_SOURCE_GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to publish public distribution releases.")
    return token


def sync_icon(app: dict) -> str:
    token = source_token()
    path = urllib.parse.quote(app["iconPath"], safe="/")
    url = f"{API_ROOT}/repos/{OWNER}/{app['repo']}/contents/{path}?ref=main"
    try:
        contents = request_json(url, token=token)
        raw = base64.b64decode(contents["content"], validate=False)
        if not raw:
            raise RuntimeError(f"The source icon is empty for {app['name']}.")
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        (ICON_DIR / app["iconFile"]).write_bytes(raw)
    except Exception:
        existing = ICON_DIR / app["iconFile"]
        if existing.exists() and existing.stat().st_size:
            print(f"{app['name']}: source icon unavailable; keeping the public copy.")
        else:
            raise
    return f"https://raw.githubusercontent.com/{DIST_REPO}/main/icons/{app['iconFile']}"


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


def distribution_release(app: dict, source_release: dict, metadata: dict[str, str], asset: dict,
                         notes: list[str]) -> dict:
    target_token = distribution_token()
    tag = f"dist-{app['repo'].lower()}-{source_release['tag_name']}"
    encoded_tag = urllib.parse.quote(tag, safe="")
    release_url = f"{API_ROOT}/repos/{DIST_REPO}/releases/tags/{encoded_tag}"
    release = maybe_json(release_url, token=target_token)
    body = distribution_notes(app, source_release, metadata, notes)

    if release is None:
        payload = {
            "tag_name": tag,
            "target_commitish": "main",
            "name": f"{app['name']} {metadata['Source-Version']} ({metadata['Source-Build-Version']})",
            "body": body,
            "draft": False,
            "prerelease": False,
        }
        try:
            release = request_json(
                f"{API_ROOT}/repos/{DIST_REPO}/releases",
                token=target_token,
                data=json.dumps(payload).encode("utf-8"),
                method="POST",
            )
        except urllib.error.HTTPError as error:
            if error.code != 422:
                raise
            release = request_json(release_url, token=target_token)

    existing_assets = {item["name"]: item for item in release.get("assets", [])}
    current = existing_assets.get(app["asset"])
    if current:
        if current.get("size") != asset.get("size"):
            raise RuntimeError(
                f"Distribution asset size mismatch for {tag}/{app['asset']}; refusing to replace it."
            )
        if release.get("body") != body:
            request_json(f"{API_ROOT}/repos/{DIST_REPO}/releases/{release['id']}", token=target_token,
                         data=json.dumps({"body": body}).encode("utf-8"), method="PATCH")
        return release

    print(f"Copying {app['name']} {metadata['Source-Version']} build {metadata['Source-Build-Version']} ({asset['size']} bytes).")
    source_bytes = request(
        asset["url"],
        token=source_token(),
        accept="application/octet-stream",
    )
    if len(source_bytes) != asset["size"]:
        raise RuntimeError(
            f"Downloaded asset size mismatch for {app['repo']} {source_release['tag_name']}: "
            f"expected {asset['size']}, got {len(source_bytes)}."
        )
    upload_url = release["upload_url"].split("{", 1)[0]
    upload_url += "?name=" + urllib.parse.quote(app["asset"], safe="")
    request(
        upload_url,
        token=target_token,
        accept="application/vnd.github+json",
        content_type="application/octet-stream",
        data=source_bytes,
        method="POST",
    )
    return request_json(release_url, token=target_token)


def eligible_source_releases(releases: list[dict], app: dict) -> list[tuple]:
    eligible = []
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
        if not asset or not asset.get("url") or not asset.get("size"):
            continue
        published = release.get("published_at")
        if not published:
            continue
        eligible.append((published, release, metadata, asset))

    eligible.sort(key=lambda item: item[0], reverse=True)
    return eligible


def app_versions(app: dict) -> list[dict]:
    url = f"{API_ROOT}/repos/{OWNER}/{app['repo']}/releases?per_page=100"
    token = source_token()
    try:
        releases = request_json(url, token=token)
    except urllib.error.HTTPError as error:
        if app.get("private") and error.code in (401, 403, 404):
            raise SourceReleaseUnavailable(
                f"No access to private source releases for {app['name']} ({error.code})."
            ) from error
        raise
    eligible = eligible_source_releases(releases, app)
    if not eligible and token and not app.get("private"):
        # SOURCE_REPOS_TOKEN can be scoped to only some repositories. For a
        # public source repo, retry without credentials so a restricted token
        # can't hide releases that the feed can read anonymously.
        print(f"{app['name']}: no eligible release with source token; retrying public release lookup.")
        releases = request_json(url)
        eligible = eligible_source_releases(releases, app)
    if not eligible:
        raise SourceReleaseUnavailable(f"No eligible source release found for {app['name']}.")

    versions = []
    for published, source_release, metadata, asset in eligible[:RELEASE_LIMIT]:
        try:
            notes = human_release_notes(app, source_release, metadata)
        except ReleaseNotesUnavailable as error:
            print(f"::warning::{error}")
            continue
        mirrored = distribution_release(app, source_release, metadata, asset, notes)
        download_url = (
            f"https://github.com/{DIST_REPO}/releases/download/"
            f"{urllib.parse.quote(mirrored['tag_name'], safe='')}/"
            f"{urllib.parse.quote(app['asset'], safe='')}"
        )
        version = {
            "version": metadata["Source-Version"],
            "buildVersion": metadata["Source-Build-Version"],
            "date": published,
            "localizedDescription": "\n".join(f"• {note}" for note in notes),
            "downloadURL": download_url,
            "size": asset["size"],
        }
        minimum_os = metadata.get("Source-Minimum-OS-Version")
        if minimum_os and minimum_os != "unknown":
            version["minOSVersion"] = minimum_os
        versions.append((published, version))

    if not versions:
        raise ReleaseNotesUnavailable(f"No release with written notes is ready for {app['name']}.")
    print(f"{app['name']}: {len(versions)} mirrored main build(s) with written release notes")
    return [version for _, version in versions]


def app_versions_or_existing(app: dict, existing_apps: list[dict]) -> list[dict]:
    try:
        return app_versions(app)
    except SourceReleaseUnavailable as error:
        if not app.get("private") and not isinstance(error, ReleaseNotesUnavailable):
            raise
        existing = next(
            (item for item in existing_apps if item.get("bundleIdentifier") == app["bundle"]),
            None,
        )
        versions = existing.get("versions") if existing else None
        if not versions:
            raise
        print(
            f"{app['name']}: no publishable update; preserving "
            f"{len(versions)} existing feed build(s). ({error})"
        )
        return versions


def main() -> None:
    current = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    apps = []
    icon_urls = {}
    for config in REPOSITORIES:
        if config["iconFile"] not in icon_urls:
            icon_urls[config["iconFile"]] = sync_icon(config)
        versions = app_versions_or_existing(config, current.get("apps", []))
        apps.append(
            {
                "name": config["name"],
                "bundleIdentifier": config["bundle"],
                "developerName": "NullDev85",
                "subtitle": config["subtitle"],
                "localizedDescription": config["description"],
                "iconURL": icon_urls[config["iconFile"]],
                "tintColor": config["tint"],
                "category": config["category"],
                "versions": versions,
            }
        )
    current["apps"] = apps
    current["featuredApps"] = [app["bundleIdentifier"] for app in apps]
    current["subtitle"] = "NullSign, Lineup for iPhone and Apple TV, and Aether"
    current["description"] = "Unsigned iOS and tvOS app builds published after successful main-branch builds."
    current["iconURL"] = f"https://raw.githubusercontent.com/{DIST_REPO}/main/icons/{SOURCE_ICON}"
    FEED_PATH.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(apps)} app entries from completed main-branch releases.")


if __name__ == "__main__":
    main()
