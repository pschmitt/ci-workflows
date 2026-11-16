# F-Droid metadata archive

An app describes itself for the F-Droid publisher with a versioned archive,
`fdroid-metadata.zip`, attached to the same GitHub release as its APKs. The
publisher (the owner's F-Droid repository service) imports it; this repository
only builds it.

## Source layout

Commit one directory per package under `fdroid/` in the app repository:

```
fdroid/<package>/metadata.yml
fdroid/<package>/icon.png          optional, square PNG, 48 to 1024 pixels
```

`metadata.yml` accepts only these optional keys:

| Key | Rule |
|---|---|
| `name` | at most 50 characters |
| `summary` | at most 80 characters |
| `description` | at most 4000 characters, plain text |
| `license` | SPDX identifier or expression (`GPL-3.0-or-later`, `Apache-2.0 OR MIT`) |
| `categories` | one to three distinct F-Droid categories |

Anything else (signing keys, build recipes, URLs, icon paths) is rejected. The
publisher alone decides which packages it trusts, from which release, and with
which signer; an archive can only describe an app.

## Archive schema 1

```
manifest.yml                           schema: 1
metadata/<package>/metadata.yml
metadata/<package>/en-US/icon.png
```

At most 2 MiB and 64 entries; YAML members at most 64 KiB, the icon at most
1 MiB. Only regular files at exactly these paths are allowed (no directory
entries, symlinks, encryption or duplicates). A new schema gets a new `schema`
number.

## Building it

`release.yaml` runs the `.github/actions/fdroid-metadata` composite action when
the caller's `fdroid-metadata-directory` (default `fdroid`) exists, writes the
archive next to the APKs, and covers it with `SHA256SUMS` and the build
provenance attestation. A missing directory skips the step; an invalid source
fails the build, so mistakes surface in the app's CI and not in production. The
archive is reproducible (sorted entries, fixed timestamps).

Callers that do not use `release.yaml` run the action themselves:

```yaml
- uses: pschmitt/ci-workflows/.github/actions/fdroid-metadata@main
  with:
    directory: fdroid
    output-directory: dist   # add dist/fdroid-metadata.zip to the release files
```

A rolling `latest` release that vacuums stale assets must keep the archive in
its asset directory, which `release.yaml` does.
