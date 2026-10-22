import importlib.util
import unittest
from pathlib import Path


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

        update_feed.source_token = lambda: "scoped-source-token"
        update_feed.request_json = fake_request_json
        update_feed.distribution_release = lambda app, source, metadata, asset: {
            "tag_name": "dist-nullsports-source-tvos-39762082363"
        }

        versions = update_feed.app_versions(app)

        self.assertEqual(requests, ["scoped-source-token", ""])
        self.assertEqual(versions[0]["buildVersion"], "87")
        self.assertEqual(
            versions[0]["downloadURL"],
            "https://github.com/nulldev85/AppSource/releases/download/"
            "dist-nullsports-source-tvos-39762082363/Lineup-tvOS-unsigned.ipa",
        )


if __name__ == "__main__":
    unittest.main()
