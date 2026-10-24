# ci-workflows

Reusable GitHub Actions workflows and scripts shared by my repositories that
ship a browser extension next to a tool ([rbw](https://github.com/pschmitt/rbw),
[browser-daemon](https://github.com/pschmitt/browser-daemon),
[bruvtab](https://github.com/pschmitt/bruvtab)).

| Workflow | What it does |
|---|---|
| `sign-extension.yaml` | Signs the extension for a version tag (Firefox via AMO, Chromium as a CRX3), reusing the tag's release assets when they match the source (AMO signs a version only once). Produces the `browser-extensions` artifact. |
| `pin-release.yaml` | Writes the release assets' version and SHA-256 to `browser/packages/metadata.json` on the default branch; the Nix packages fetch the assets by those hashes. |
| `verify-pin.yaml` | CI check: the pinned assets match their hashes and the pinned tag's source. |

| `rust-lint.yaml` | rustfmt, clippy (`-D warnings`) and optionally cargo-deny. |
| `extension-lint.yaml` | Builds the extension, runs the repository's checks and `web-ext lint`. |
| `release-script.yaml` | Fails when `tools/release.sh` differs from `scripts/release.sh` here. |

`scripts/verify-extension.py` is the check both signing and verification use.
`scripts/release.sh` is the release tool (`prepare VERSION`, `tag`); each repository
carries a verbatim copy in `tools/release.sh` and, if its version lives somewhere
other than `Cargo.toml`, a `tools/release-hooks.sh`.
Callers pin these with `uses: pschmitt/ci-workflows/.github/workflows/<name>.yaml@main`.
