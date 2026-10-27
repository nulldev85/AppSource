# NullDev App Source

This public repository hosts the AltStore-compatible source for NullSign,
Lineup for iPhone, Lineup for Apple TV, and Aether. Add this URL in AltStore or
Feather:

`https://raw.githubusercontent.com/nulldev85/AppSource/main/apps.json`

The feed includes only unsigned IPAs attached to verified `source-*` releases
from successful builds on each app repository's `main` branch. The updater
copies those IPAs into public releases in this repository and keeps the app
icons here, so signer downloads do not depend on the app source repositories
being public. Pull request builds, manual branch builds, simulator packages,
and failed or unfinished builds are not included.

Each IPA is published under its app, version and build, such as
`Lineup-iPhone-0.19.0-956.ipa`, so a downloaded file says which build it is.
Builds mirrored before that keep the name they were first published under.

The source's own icon, `icons/source.png`, is "Null's Apps" in the website's
dot font. It lives only here, so the updater never replaces it; to change it,
edit and run `fonts/icon.py` in `nulldev85/nulldev85.github.io`.

## Release notes

Every distributed build needs a short, written list of what changed for users.
Keep the wording natural and specific: say what someone can do now or which
problem they should stop running into. Avoid commit titles, compiler errors,
internal implementation details, vague polish claims and promises about things
that were not tested. Keep iPhone and Apple TV changes separate.

Add notes to `release-notes.json` before a build reaches distribution. Match the
bundle identifier, version, build number and **full source commit SHA**; a build
number alone is not enough because it can be reused. Alternatively, the source
release can include an explicitly written `## What's new` section with bullets.
The updater never manufactures notes from a commit log or build output.

These notes are used for the public release, the signer feed and the website.
Older mirrored releases receive note-only corrections without replacing their
IPAs, tags or release dates. If a new build has no written notes, the updater
leaves it out of the feed, reports the missing notes in Actions, and keeps the
previous published builds available. Add its notes and rerun the feed update;
there is no need to rebuild the app. Scheduled updates still run every 30 minutes.

## Making the app source repositories private

Before changing `NullSign`, `NullSports`, or `Aether` to private, add a fine-
grained personal access token as the `SOURCE_REPOS_TOKEN` Actions secret in
this repository. Give it read-only Contents access to those three repositories.
The updater uses it only to read releases, IPA files, and current app icons;
`GITHUB_TOKEN` writes the public copies and feed to this repository. Do not put
the token in this repo's files or the feed.

After saving the secret, run **Actions → Update app source feed → Run workflow**
once and confirm it succeeds before changing repository visibility. Scheduled
updates run every 30 minutes. Without the secret, already mirrored apps stay
available, but new private-repository builds cannot be copied into the public
feed.

The public IPAs remain downloadable and can be inspected or reverse engineered;
this setup keeps the app source code private while allowing testers to install
the unsigned builds with their signer.
