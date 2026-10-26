import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "update_feed.py"
SPEC = importlib.util.spec_from_file_location("release_notes_feed", SCRIPT)
feed = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feed)


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.app = {"name": "Lineup tvOS", "repo": "NullSports",
                    "bundle": "com.nulldev85.NullSports", "asset": "Lineup-tvOS-unsigned.ipa"}
        self.metadata = {
            "Source-App": "Lineup tvOS", "Source-Bundle-Identifier": self.app["bundle"],
            "Source-Version": "0.19.0", "Source-Build-Version": "99",
            "Source-Minimum-OS-Version": "18.0", "Source-Branch": "main",
            "Source-SHA": "e5fd885cd9db65ac2984db6142f0757bfbab43ef",
        }
        self.release = {"tag_name": "source-tvos-fixture", "body": "\n".join(
            f"{key}: {value}" for key, value in self.metadata.items())}

    def test_catalog_is_valid_and_latest_platform_notes_do_not_mix(self):
        records = feed.release_note_catalog()
        tv = feed.human_release_notes(self.app, self.release, self.metadata)
        phone_app = {**self.app, "name": "Lineup", "bundle": "com.nulldev85.NullSports.iOS"}
        phone = {**self.metadata, "Source-App": "Lineup", "Source-Bundle-Identifier": phone_app["bundle"],
                 "Source-Build-Version": "154"}
        ios = feed.human_release_notes(phone_app, self.release, phone)
        self.assertTrue(any("Search again" in note for note in ios))
        self.assertFalse(any("Search again" in note for note in tv))
        self.assertEqual(len(records), 13)

    def test_same_version_and_build_with_a_different_commit_does_not_borrow_notes(self):
        other = {**self.metadata, "Source-SHA": "a" * 40}
        with self.assertRaises(feed.ReleaseNotesUnavailable):
            feed.human_release_notes(self.app, self.release, other)

    def test_explicit_source_notes_are_accepted_without_copying_build_details(self):
        release = {"body": "## What's new\n\n- Fixed the Search button returning to the wrong page.\n\n"
                   "## Build details\nSource-SHA: " + "a" * 40}
        notes = feed.human_release_notes(self.app, release, {**self.metadata, "Source-SHA": "a" * 40})
        self.assertEqual(notes, ["Fixed the Search button returning to the wrong page."])

    def test_diagnostics_and_placeholders_cannot_become_user_notes(self):
        for note in ["error: invalid redeclaration of actual", "Source-SHA: abcdef1234567890",
                     "Release notes for this build are being prepared.", "xcodebuild returned status 65"]:
            with self.subTest(note=note), self.assertRaises(ValueError):
                feed.checked_notes([note])

    def test_distribution_body_keeps_machine_metadata_separate_and_parseable(self):
        notes = feed.human_release_notes(self.app, self.release, self.metadata)
        body = feed.distribution_notes(self.app, self.release, self.metadata, notes)
        self.assertTrue(body.startswith("## What's new\n"))
        self.assertLess(body.index(notes[0]), body.index("## Build details"))
        restored = feed.release_metadata(body)
        for key, value in self.metadata.items():
            self.assertEqual(restored[key], value)
        self.assertEqual(restored["Source-Origin-Tag"], self.release["tag_name"])

    def test_correcting_existing_notes_does_not_replace_the_ipa(self):
        mirrored = {"id": 123, "body": "Old technical-only notes", "published_at": "2026-10-26T00:00:00Z",
                    "assets": [{"id": 456, "name": self.app["asset"], "size": 1234}]}
        notes = feed.human_release_notes(self.app, self.release, self.metadata)
        with (patch.object(feed, "distribution_token", return_value="fixture"),
              patch.object(feed, "maybe_json", return_value=mirrored),
              patch.object(feed, "request_json", return_value=mirrored) as update,
              patch.object(feed, "request") as download):
            result = feed.distribution_release(self.app, self.release, self.metadata, {"size": 1234}, notes)
        self.assertEqual(result["assets"], mirrored["assets"])
        self.assertEqual(result["published_at"], mirrored["published_at"])
        download.assert_not_called()
        self.assertEqual(update.call_count, 1)
        self.assertEqual(update.call_args.kwargs["method"], "PATCH")
        payload = json.loads(update.call_args.kwargs["data"])
        self.assertEqual(set(payload), {"body"})
        self.assertIn(notes[0], payload["body"])

    def test_identical_notes_are_not_patched_again(self):
        notes = feed.human_release_notes(self.app, self.release, self.metadata)
        mirrored = {"id": 123, "body": feed.distribution_notes(self.app, self.release, self.metadata, notes),
                    "assets": [{"name": self.app["asset"], "size": 1234}]}
        with (patch.object(feed, "distribution_token", return_value="fixture"),
              patch.object(feed, "maybe_json", return_value=mirrored),
              patch.object(feed, "request_json") as update):
            feed.distribution_release(self.app, self.release, self.metadata, {"size": 1234}, notes)
        update.assert_not_called()

    def test_unknown_new_release_keeps_the_existing_public_feed_available(self):
        previous = [{"version": "0.19.0", "buildVersion": "99", "localizedDescription": "• A written update."}]
        with patch.object(feed, "app_versions", side_effect=feed.ReleaseNotesUnavailable("Needs notes")):
            result = feed.app_versions_or_existing(self.app, [{"bundleIdentifier": self.app["bundle"], "versions": previous}])
        self.assertEqual(result, previous)

    def test_feed_uses_written_notes_and_skips_a_newer_build_with_only_diagnostics(self):
        known = {**self.release, "draft": False, "prerelease": False,
                 "published_at": "2026-10-26T00:00:00Z",
                 "assets": [{"name": self.app["asset"], "url": "https://example.invalid/ipa", "size": 1234}]}
        unknown = {**known, "tag_name": "source-newer", "published_at": "2026-10-27T00:00:00Z",
                   "body": known["body"].replace(self.metadata["Source-SHA"], "a" * 40)
                   + "\n\n## What's new\n- error: invalid redeclaration of actual"}
        with (patch.object(feed, "source_token", return_value="fixture"),
              patch.object(feed, "request_json", return_value=[unknown, known]),
              patch.object(feed, "distribution_release", return_value={"tag_name": "dist-known"}) as mirror):
            versions = feed.app_versions(self.app)
        self.assertEqual(len(versions), 1)
        self.assertEqual(mirror.call_count, 1)
        description = versions[0]["localizedDescription"]
        self.assertTrue(description.startswith("• "))
        self.assertIn("logos", description)
        self.assertNotIn("Source-SHA", description)
        self.assertNotIn("error:", description)
        self.assertNotIn(self.metadata["Source-SHA"][:7], description)

    def test_duplicate_commit_entries_are_rejected(self):
        record = feed.release_note_catalog()[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "release-notes.json"
            path.write_text(json.dumps({"schemaVersion": 1, "releases": [record, record]}), encoding="utf-8")
            with patch.object(feed, "NOTES_PATH", path), self.assertRaises(ValueError):
                feed.release_note_catalog()


if __name__ == "__main__":
    unittest.main()
