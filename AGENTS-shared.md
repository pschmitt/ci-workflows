# Shared AGENTS.md conventions for the Android app fleet

Pulled in as a git submodule at `.just/android-app-ci` in each app repo (see this repo's README).
Each app's own `AGENTS.md` references the relevant section(s) below instead of repeating them -
read this file too, not just the app's own `AGENTS.md`. Sections an app doesn't use (e.g. a
physical device it has no recipes for) don't apply to it; its own `AGENTS.md` says which do.

## Task tracking

- `TODO.md` is the running backlog/changelog for this project, one `## <PREFIX>-N:` entry per
  feature or fix (see the app's own `AGENTS.md` for its exact prefix), numbered sequentially
  (never reuse or renumber an id). Each entry has a checklist of sub-items (`- [ ]`/`- [x]`) and
  ends with a `Status:` line (`not started` / `in progress` / `mostly done` / `**done**`, plus a
  date and how it was verified).
- Before starting any non-trivial new feature or fix, add (or update) a `<PREFIX>-N` entry
  describing it - even if the same conversation immediately goes on to implement it. Update the
  checklist/status as work actually lands, rather than writing the whole entry retroactively once
  everything's finished. This keeps `TODO.md` an accurate record of what's done vs. still open,
  and lets another agent (or a future you) resume the work cold from just this file.
- Trivial one-off asks (a typo, a single-line tweak) don't need their own entry.

## Dev environment

- `nix develop` provides the full toolchain (JDK 21, Android SDK, `just`, `ktfmt`) and installs
  the repo's pre-commit hooks (see `flake.nix`'s `git-hooks.nix` integration, wired through
  `nix/devshells.nix` in this repo - trailing whitespace, EOF fixer, merge-conflict/large-file
  checks, `nixfmt`, `statix`). The generated `.pre-commit-config.yaml` is gitignored - it's
  regenerated from `flake.nix` on every shell entry, don't hand-edit it.
  - **ktfmt is nix-only**: the pre-commit hook, `just lint`/`just format` and CI's lint workflow
    all run the same nixpkgs `ktfmt` (kotlinlang style) from the app's own `flake.lock`, so local
    and CI formatting cannot drift. The apps do not use the ktfmt Gradle plugin (it pinned a
    different ktfmt version); `just lint` is `ktfmt --dry-run` and runs locally, no Gradle.
- Prefer the `justfile` recipes over raw `./gradlew`/`ssh`/`adb` invocations - run `just --list`
  for the full set. `nix develop`'s shellHook also auto-runs `git submodule update --init` on
  every entry, so a fresh git worktree (this fleet creates plenty for agent-driven work) never
  needs a manual submodule init step before `just` works.

## Builds

- **Never run Gradle builds locally on this machine** - always build on `rofl-13.brkn.lol` or
  `rofl-14.brkn.lol` instead (see the app's own `justfile`/`AGENTS.md` for its exact recipe names
  and any module-specific flags).
- **CI is the sole authority on lint/format, full stop - not `just lint`, not `just format`, not
  local judgment.** Confirmed the hard way more than once: a change that passed a local/remote
  check still failed CI's `Lint` job after being pushed. If CI's `Lint` job fails:
  - `.github/workflows/lint.yaml`'s `ktfmt` job auto-uploads a `ktfmt-diff-patch` artifact
    whenever the ktfmt check fails - on any trigger, push/PR or manual (`gh workflow run
    lint.yaml` to get one preemptively). It contains exactly what the flake's `ktfmt` would
    change. Normally the pre-commit hook already prevents this; if it does fail, grab it with
    `gh run download <run-id> -n ktfmt-diff-patch` and apply it (`git apply`) rather than
    guessing or reformatting by hand.
  - Fix every lint/format violation CI reports before calling a change done, even in files the
    current change didn't touch or author - don't scope a fix to "only the lines I changed" if CI
    flags something adjacent. Never disable, skip, or baseline around a lint failure to make it
    go away; fix the actual violation.
  - `just format` runs the flake's `ktfmt` over every tracked `.kt`/`.kts` file; since it is the
    same binary as the hook and CI it is authoritative, and on a formatted tree it changes nothing.
- Never tag a release from a commit whose CI hasn't gone green on that exact commit's SHA - not
  an assumption, not an older green run. `gh run list --branch main --limit 5` (check the commit
  SHA column) or `gh run list --commit <sha>`. If a tag was already pushed and CI on it fails,
  delete the tag (`git push origin :refs/tags/<tag>`) and recreate it once a fixed commit is
  fully green - never leave a released tag pointing at a red build.

## Physical test devices

Use the device-specific recipes in the app's `justfile` and follow the private `brkn-infra` skill
for connection details and host-specific setup. Do not add private hostnames, addresses, device
names, or topology details to this shared file.

- **Deploy to every device an app targets** after a verified change (compiled, tested, and
  lint-checked remotely). Use the app's `deploy-all` recipe when available. Target a single device
  only for a specific reason, such as reproducing a device-specific bug.
- If installation fails with `INSTALL_FAILED_UPDATE_INCOMPATIBLE`, the installed app was signed
  with a different key. Uninstalling and reinstalling fixes this, but wipes local app data (such as
  a Room database, saved credentials, or tokens). Confirm with the user before doing this if the
  device may contain data they care about.
