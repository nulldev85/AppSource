# NullDev App Source

This repository hosts the AltStore-compatible source for NullSign, Lineup, and
Aether. Add this URL in AltStore or Feather:

`https://raw.githubusercontent.com/nulldev85/AppSource/main/apps.json`

The feed includes only public IPA assets from `source-*` releases created after
successful builds on each app repository's `main` branch. Pull request builds,
manual branch builds, simulator packages, and failed or unfinished builds are
not included. The IPAs are unsigned and must be signed with NullSign, Feather,
or another compatible signer before installation.

The scheduled updater reads public GitHub Releases, not Actions build status.
It never needs a token for the three app repositories. Release history is kept
in each app repository; the source lists up to 20 recent source builds per app.
