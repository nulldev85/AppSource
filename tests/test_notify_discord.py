import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "notify_discord.py"
SPEC = importlib.util.spec_from_file_location("notify_discord", SCRIPT)
discord = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(discord)


class DiscordReleaseNotificationTests(unittest.TestCase):
    def _feed(self, ios_build="1224", ios_date="2026-11-21T03:50:40Z", tv_build="964", tv_date="2026-11-21T03:37:18Z"):
        return {
            "apps": [
                {
                    "name": "Lineup",
                    "bundleIdentifier": "com.nulldev85.NullSports.iOS",
                    "iconURL": "https://raw.githubusercontent.com/nulldev85/AppSource/main/icons/lineup.png",
                    "versions": [
                        {
                            "version": "0.19.0",
                            "buildVersion": ios_build,
                            "date": ios_date,
                            "localizedDescription": "• Faster Live Stats sync.\n• Cleaner Library hero.",
                            "size": 39_846_892,
                        }
                    ],
                },
                {
                    "name": "Lineup tvOS",
                    "bundleIdentifier": "com.nulldev85.NullSports",
                    "iconURL": "https://raw.githubusercontent.com/nulldev85/AppSource/main/icons/lineup.png",
                    "versions": [
                        {
                            "version": "0.19.0",
                            "buildVersion": tv_build,
                            "date": tv_date,
                            "localizedDescription": "• Faster Live Stats sync on Apple TV.",
                            "size": 51_962_962,
                        }
                    ],
                },
            ]
        }

    def test_detects_only_genuinely_newer_builds(self):
        prev = self._feed()
        same = self._feed()
        self.assertEqual(discord.new_releases(prev, same), [])

        updated = self._feed(ios_build="1231", ios_date="2026-11-21T23:17:42Z")
        found = discord.new_releases(prev, updated)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0]["bundleIdentifier"], "com.nulldev85.NullSports.iOS")
        self.assertEqual(found[0][1]["buildVersion"], "1231")

    def test_older_rollback_is_not_reannounced(self):
        prev = self._feed(ios_build="1231", ios_date="2026-11-21T23:17:42Z")
        older = self._feed(ios_build="1224", ios_date="2026-11-21T03:50:40Z")
        self.assertEqual(discord.new_releases(prev, older), [])

    def test_embed_uses_site_link_not_github_and_optional_role_ping(self):
        feed = self._feed(ios_build="1231", ios_date="2026-11-21T23:17:42Z")
        app = feed["apps"][0]
        release = app["versions"][0]

        no_ping = discord.build_payload(app, release)
        self.assertNotIn("content", no_ping)
        self.assertEqual(no_ping["allowed_mentions"], {"parse": []})
        embed = no_ping["embeds"][0]
        self.assertEqual(embed["title"], "Lineup 0.19.0 (1231)")
        self.assertEqual(embed["url"], "https://nulldev85.github.io/#lineup")
        self.assertNotIn("github.com", str(embed["fields"]))
        self.assertIn("Faster Live Stats sync.", embed["description"])

        with_ping = discord.build_payload(app, release, role_id="999888777")
        self.assertEqual(with_ping["content"], "<@&999888777>")
        self.assertEqual(with_ping["allowed_mentions"], {"parse": [], "roles": ["999888777"]})

    def test_rejects_non_discord_webhook_urls(self):
        with self.assertRaises(ValueError):
            discord.post_webhook("https://example.com/hook", {"embeds": []})


if __name__ == "__main__":
    unittest.main()
