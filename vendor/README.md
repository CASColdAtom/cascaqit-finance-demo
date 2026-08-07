# CASCAQit CI wheel

This directory contains the CASCAQit wheel required by the GitHub Chromium
acceptance workflow. The SDK repository is private and the demo repository's
default `GITHUB_TOKEN` cannot check it out, so CI uses the same immutable SDK
release as the offline product build.

| Field | Value |
|---|---|
| Source tag | `v1.0.7a` |
| Source commit | `2fa67d0c2fdb447995233ab3b65cc92897e81ec5` |
| Wheel | `cascaqit-1.0.7a0-py3-none-any.whl` |
| Wheel SHA-256 | `c6aab02a71e0897d569c3c9f6aebf336b2886daf71be1ed1443a26640defecf6` |
| License | Apache-2.0, included in the wheel |

The workflow verifies this checksum before installation. Replace the wheel,
source commit, checksum, and workflow pin together when upgrading CASCAQit.
