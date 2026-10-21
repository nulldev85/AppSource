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
