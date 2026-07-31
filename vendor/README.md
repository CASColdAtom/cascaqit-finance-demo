# CASCAQit CI wheel

This directory contains the CASCAQit wheel required by the GitHub Chromium
acceptance workflow. The SDK repository is private and the demo repository's
default `GITHUB_TOKEN` cannot check it out, so CI uses the same immutable SDK
release as the offline product build.

| Field | Value |
|---|---|
| Source tag | `v1.0.5a` |
| Source commit | `6a7df7a2f6f611b1e5f4b3377bc7631a6ff69853` |
| Wheel | `cascaqit-1.0.5a0-py3-none-any.whl` |
| Wheel SHA-256 | `af665bcd8dc81d7afe1370c1acee656dcc3192b63552429692655dc0159ee97e` |
| License | Apache-2.0, included in the wheel |

The workflow verifies this checksum before installation. Replace the wheel,
source commit, checksum, and workflow pin together when upgrading CASCAQit.
