# ci-workflows

Reusable GitHub Actions workflows, actions and scripts shared by my repositories.
The extension workflows serve projects including [rbw](https://github.com/pschmitt/rbw),
[browser-daemon](https://github.com/pschmitt/browser-daemon),
and [bruvtab](https://github.com/pschmitt/bruvtab).

| Workflow | What it does |
|---|---|
| `sign-extension.yaml` | Signs the extension for a version tag (Firefox via AMO, Chromium as a CRX3), reusing the tag's release assets when they match the source (AMO signs a version only once). Produces the `browser-extensions` artifact. |
| `pin-release.yaml` | Writes the release assets' version and SHA-256 to `browser/packages/metadata.json` on the default branch; the Nix packages fetch the assets by those hashes. |
| `verify-pin.yaml` | CI check: the pinned assets match their hashes and the pinned tag's source. |

| `rust-lint.yaml` | rustfmt, clippy (`-D warnings`) and optionally cargo-deny. |
| `extension-lint.yaml` | Builds the extension, runs the repository's checks and `web-ext lint`. |
| `nix-aarch64.yaml` | Builds a flake's aarch64-linux packages and checks natively on an arm runner and pushes them to the niks3 S3 cache with a GitHub OIDC token (main pins `<pin-prefix>-<package>-<n>`, pull requests push unpinned). The caller needs `id-token: write`, the variable `NIKS3_SERVER_URL`, and the server must trust the repository. It reads the same bucket as a substituter when the caller passes the read-only `s3_store`, `s3_access_key` and `s3_secret_key` secrets, and keeps a Nix store cache for main. |
| `release-script.yaml` | Fails when `tools/release.sh` differs from `scripts/release.sh` here. |

`scripts/verify-extension.py` is the check both signing and verification use.
`scripts/release.sh` is the release tool (`prepare VERSION`, `tag`); each repository
carries a verbatim copy in `tools/release.sh` and, if its version lives somewhere
other than `Cargo.toml`, a `tools/release-hooks.sh`.
Callers pin these with `uses: pschmitt/ci-workflows/.github/workflows/<name>.yaml@main`.

Repositories with `nixbot.toml` also wait for successful `nixbot/nix-eval` and
`nixbot/nix-build` checks on the exact commit before the release helper tags it.

## Python

After checkout, `.github/actions/python-lint` sets up the requested Python
version and runs Flake8 and Black. For example:

```yaml
- uses: actions/checkout@v7
- uses: pschmitt/ci-workflows/.github/actions/python-lint@main
  with:
    python-version: '3.15'
```

For Home Assistant integrations using `setup-uv@v5`, the
`.github/actions/homeassistant-ruff-v5` composite runs `uvx ruff check .` and
`uvx ruff format --check .` after the caller checks out its code. Keep the
Hassfest job and repository-specific tests in the caller.

## Android

The Android interfaces were brought over from
[android-app-ci](https://github.com/pschmitt/android-app-ci). See the
[provenance and license notice](ANDROID-CI-NOTICE.md) and the
[Android caller examples and input documentation](docs/android-ci.md).
Existing callers can continue using the original repository during migration.

| Workflow | Purpose |
|---|---|
| `build.yaml` | Debug build, unit tests and APK artifacts. |
| `lint.yaml` | ktfmt and Android Lint. |
| `release.yaml` | Signed APK release and attestations. |
| `play-store.yaml` | AAB build and gated Play Store publishing. |
| `play-store-assets.yaml` | Upload Play Store listing assets. |
| `screenshots-open-pr.yaml` | Collect screenshot artifacts and open or update a PR. |

Call these through `pschmitt/ci-workflows/.github/workflows/<name>.yaml@main`.
Composite actions live in `.github/actions/`; screenshot capture remains in
the caller, and can invoke `scripts/wait-for-android-emulator.sh` inside the
emulator runner. Shared Just recipes and the Nix devShell helper remain at
`just/` and `nix/devshells.nix` for existing integration patterns. Review each
workflow's inputs, permissions and secrets before changing a caller.
