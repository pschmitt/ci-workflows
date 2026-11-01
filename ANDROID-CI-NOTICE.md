# Android CI workflow provenance

The Android workflows, composite actions, shared Just recipes, Nix devShell builder, emulator
readiness script, and shared agent guidance in this repository were copied from
[pschmitt/android-app-ci](https://github.com/pschmitt/android-app-ci), source commit
`5f6ff4a477d6c221d7f37c38a47c0f7f65ff817d`, on 2026-11-01. The workflow
and script references to the canonical repository were updated to `pschmitt/ci-workflows`; the
shared Just and Nix assets retain their existing interfaces for consuming app repositories. The
physical-device section of `AGENTS-shared.md` was generalized to avoid publishing private
infrastructure details.

These Android CI files are distributed under GNU GPL version 3 or later. The complete license text
is in [LICENSE.android-app-ci](LICENSE.android-app-ci).
