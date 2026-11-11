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
| `nix-lint.yaml` | statix, deadnix and nixfmt over every tracked Nix file, with the linters from the caller's locked nixpkgs. The caller owns the triggers and should run on `**.nix` and `flake.lock`. |
| `nix-aarch64.yaml` | Builds a flake's aarch64-linux packages and checks natively on an arm runner and pushes them to the niks3 S3 cache with a GitHub OIDC token (main pins `<pin-prefix>-<package>-<n>`, pull requests push unpinned). For crane packages it also pushes their dependency build and vendored sources (`cargoArtifacts`, `cargoVendorDir`, pinned as `<pin-prefix>-<package>-<input>-<n>`), so a source change does not rebuild every dependency. The caller needs `id-token: write`, the variable `NIKS3_SERVER_URL`, and the server must trust the repository. It reads the same bucket as a substituter (trusting the keys its paths are signed with, `s3-public-keys`) when the caller passes the read-only `s3_store`, `s3_access_key` and `s3_secret_key` secrets and keeps a Nix store cache for main. `exclude` leaves out packages and `exclude-checks` flake checks that cannot run there (NixOS VM tests: the runners have no KVM). |
| `nix-hash-fixup.yaml` | On a dependency-update pull request (Renovate), refreshes the fixed-output hashes of the given flake `packages` with `nix-update --version=skip` (npmDepsHash, cargoHash, vendorHash, ...) and commits them to the pull request branch. With `playwright-dir`, it first pins that package's `@playwright/test` to the flake's nixpkgs `playwright-driver` version. It pushes as the `pschmitt-ci` GitHub App (secrets `app_id`, `app_private_key`; the app needs Contents read & write on the repository) so the pull request's checks run again; forks are skipped. Callers trigger it on `pull_request` for their lockfiles and list the bot (`<id>+pschmitt-ci[bot]@users.noreply.github.com`) in Renovate's `gitIgnoredAuthors`. Logo: `docs/pschmitt-ci.svg`. |
| `release-script.yaml` | Fails when `tools/release.sh` differs from `scripts/release.sh` here. |
| `github-release.yaml` | Generates changelog text from the previous tag and creates a GitHub release. `dry-run: true` validates changelog generation without creating the release. |

`scripts/verify-extension.py` is the check both signing and verification use.
`scripts/release.sh` is the release tool (`prepare VERSION`, `tag`); each repository
carries a verbatim copy in `tools/release.sh` and, if its version lives somewhere
other than `Cargo.toml`, a `tools/release-hooks.sh`.
Callers reference these with `uses: pschmitt/ci-workflows/.github/workflows/<name>.yaml@main`.
Keep tag-push and manual-dispatch triggers in each caller; set the reusable
workflow's `dry-run` input to `true` for a safe manual validation.

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

For projects using pip and Ruff, `.github/actions/python-ruff` installs Ruff and
runs `ruff check`; set `github-output: 'true'` to emit GitHub annotations or
`format-check: 'true'` to also check formatting. Set `upgrade-pip: 'false'`
to retain the runner's existing pip version.

`python-lint` also supports `flake8-mode: custom`, an optional requirements
file, and configurable Flake8 and Black arguments. Argument strings are split
on whitespace; shell quoting and expansion are not supported. The default mode
continues to use `py-actions/flake8@v2`.

For Home Assistant integrations using `setup-uv@v5`, the
`.github/actions/homeassistant-ruff-v5` composite runs `uvx ruff check .` and
`uvx ruff format --check .` after the caller checks out its code. Keep the
Hassfest job and repository-specific tests in the caller. The
`homeassistant-ruff-v10` variant uses `setup-uv@v10.3.3` for callers already on
that version.

## Shell

`.github/actions/shellcheck` checks discovered shell files together using
`ludeeus/action-shellcheck`; the optional `ignore_names` input excludes names.
The caller performs checkout and can supply `SHELLCHECK_OPTS` in its environment.

## Nix

`nix-flake-lock.yaml` updates `flake.lock` and opens an update pull request.
The caller owns the schedule and manual trigger and must grant `contents: write`
and `pull-requests: write`. The workflow uses the default GitHub token.

To build an x86_64 Nix output once per run and reuse it in later jobs (and runs),
`.github/actions/nix-niks3` installs Nix with the niks3 S3 store as a
substituter (pass the read-only `NIKS3_S3_*` secrets; without them it is plain
Nix), and `.github/actions/niks3-push` pushes store paths there with the job's
GitHub OIDC token (needs `id-token: write` and `NIKS3_SERVER_URL`; pinned as
`<pin-prefix>-<name>` on the default branch, unpinned on pull requests, skipped
elsewhere):

```yaml
- uses: pschmitt/ci-workflows/.github/actions/nix-niks3@main
  with:
    s3-store: ${{ secrets.NIKS3_S3_STORE }}
    s3-access-key: ${{ secrets.NIKS3_S3_ACCESS_KEY }}
    s3-secret-key: ${{ secrets.NIKS3_S3_SECRET_KEY }}
- run: echo "server $(nix build --no-link --print-out-paths .#server)" > "$RUNNER_TEMP/paths"
- uses: pschmitt/ci-workflows/.github/actions/niks3-push@main
  with:
    paths: ...           # "name /nix/store/..." lines
    pin-prefix: gh-<repo>-main
    server-url: ${{ vars.NIKS3_SERVER_URL }}
```

## Docker

`docker-build.yaml` builds and publishes multi-platform images to Docker Hub
and GHCR. The caller specifies the image name and platforms, passes the Docker
Hub credentials, and grants `contents: read` and `packages: write`. For a
non-publishing build, set `publish: false`; it skips registry logins, image
pushes and cache export and can run with read-only permissions.

`docker-native.yaml` builds each platform on a native GitHub runner instead of
under QEMU (linux/amd64 on `ubuntu-latest`, linux/arm64 on
`ubuntu-24.04-arm`), pushes each by digest and joins them into one manifest per
registry (`registries`, default `["ghcr.io"]`; add `docker.io` with the Docker
Hub secrets). It tags `latest`, `sha-<commit>`, the branch on branch pushes and
the version on tag pushes, and attests the GHCR image. Use it for images that
compile native code. The caller decides `publish`; to publish it grants
`contents: read`, `packages: write`, `id-token: write` and
`attestations: write`.

```yaml
docker:
  permissions:
    contents: read
    packages: write
    id-token: write
    attestations: write
  uses: pschmitt/ci-workflows/.github/workflows/docker-native.yaml@main
  with:
    image-name: pschmitt/example
    registries: '["docker.io", "ghcr.io"]'
    publish: ${{ github.event_name != 'pull_request' && github.ref == 'refs/heads/main' }}
  secrets:
    dockerhub_username: ${{ secrets.DOCKER_USERNAME }}
    dockerhub_password: ${{ secrets.DOCKER_PASSWORD }}
```

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
