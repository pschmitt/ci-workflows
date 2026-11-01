# Agent guidance

This repository hosts reusable GitHub Actions workflows, composite actions,
and scripts shared by the owner's projects. Start with [README.md](README.md)
for the catalog and [docs/android-ci.md](docs/android-ci.md) for Android
callers. Workflows are in `.github/workflows/`; composite actions are in
`.github/actions/`.

Before changing an interface, inspect its current callers and preserve their
triggers, checks, permissions, secrets, artifacts, and release behavior. Shared
GitHub Actions references to this repository use `@main`, so changes take effect
for callers immediately. Keep repository-specific jobs local when the shared
interface does not preserve their behavior. Keep PyPI publishing in the
top-level caller: the PyPI publishing action does not support invocation from
reusable workflows or composite actions.

Run the applicable workflow and action validation checks in
`.github/workflows/validate.yaml` and check the diff for whitespace. Validate
publishing paths without creating releases, publishing packages or images, or
opening pull requests unless the task explicitly authorizes those operations.
