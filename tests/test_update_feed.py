import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_feed.py"
SPEC = importlib.util.spec_from_file_location("update_feed", SCRIPT)
update_feed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_feed)


class AppVersionLookupTests(unittest.TestCase):
    def test_retries_public_release_list_when_scoped_token_hides_build(self):
        app = {
            "repo": "NullSports",
            "name": "Lineup tvOS",
            "bundle": "com.nulldev85.NullSports",
            "asset": "Lineup-tvOS-unsigned.ipa",
        }
        release = {
            "draft": False,
            "prerelease": False,
            "tag_name": "source-tvos-39762082363",
            "body": "\n".join(
                [
                    "Source-App: Lineup tvOS",
                    "Source-Bundle-Identifier: com.nulldev85.NullSports",
                    "Source-Version: 0.19.0",
                    "Source-Build-Version: 87",
                    "Source-Branch: main",
                    "Source-SHA: c5bc676e3aa1fe6e2781ecd8f971abc539e034db",
                ]
            ),
            "assets": [
                {
                    "name": "Lineup-tvOS-unsigned.ipa",
                    "url": "https://example.invalid/Lineup-tvOS-unsigned.ipa",
                    "size": 46565766,
                }
            ],
            "published_at": "2026-10-22T15:55:55Z",
        }
        requests = []

        def fake_request_json(url, *, token="", data=None, method=None):
            requests.append(token)
            return [] if token else [release]

        with (
            patch.object(update_feed, "source_token", return_value="scoped-source-token"),
            patch.object(update_feed, "request_json", side_effect=fake_request_json),
            patch.object(
                update_feed,
                "distribution_release",
                return_value={"tag_name": "dist-nullsports-source-tvos-39762082363"},
            ),
        ):
            versions = update_feed.app_versions(app)

        self.assertEqual(requests, ["scoped-source-token", ""])
        self.assertEqual(versions[0]["buildVersion"], "87")
        self.assertEqual(
            versions[0]["downloadURL"],
            "https://github.com/nulldev85/AppSource/releases/download/"
            "dist-nullsports-source-tvos-39762082363/Lineup-tvOS-unsigned.ipa",
        )

    def test_private_source_without_visible_release_does_not_retry_public_api(self):
        app = {
            "repo": "NullSign",
            "name": "NullSign",
            "bundle": "com.elmat.NullSign",
            "asset": "NullSign-unsigned.ipa",
            "private": True,
        }
        requests = []

        def fake_request_json(url, *, token="", data=None, method=None):
            requests.append(token)
            return []

        with (
            patch.object(update_feed, "source_token", return_value="scoped-source-token"),
            patch.object(update_feed, "request_json", side_effect=fake_request_json),
        ):
            with self.assertRaises(update_feed.SourceReleaseUnavailable):
                update_feed.app_versions(app)

        self.assertEqual(requests, ["scoped-source-token"])

    def test_private_source_auth_error_is_treated_as_unavailable(self):
        app = {
            "repo": "NullSign",
            "name": "NullSign",
            "bundle": "com.elmat.NullSign",
            "asset": "NullSign-unsigned.ipa",
            "private": True,
        }
        url = "https://api.github.com/repos/nulldev85/NullSign/releases?per_page=100"

        def unauthorized(*args, **kwargs):
            raise update_feed.urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

        with (
            patch.object(update_feed, "source_token", return_value="expired-token"),
            patch.object(update_feed, "request_json", side_effect=unauthorized),
        ):
            with self.assertRaises(update_feed.SourceReleaseUnavailable):
                update_feed.app_versions(app)

    def test_private_source_keeps_previous_catalog_versions_when_unavailable(self):
        app = {
            "repo": "NullSign",
            "name": "NullSign",
            "bundle": "com.elmat.NullSign",
            "private": True,
        }
        previous_versions = [{"version": "1.4.0", "buildVersion": "29"}]
        existing_apps = [
            {"bundleIdentifier": "com.elmat.NullSign", "versions": previous_versions}
        ]

        with patch.object(
            update_feed,
            "app_versions",
            side_effect=update_feed.SourceReleaseUnavailable("not visible"),
        ):
            versions = update_feed.app_versions_or_existing(app, existing_apps)

        self.assertEqual(versions, previous_versions)


if __name__ == "__main__":
    unittest.main()
