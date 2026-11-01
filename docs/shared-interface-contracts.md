# Shared interface compatibility checks

Callers use shared workflows and actions through mutable `@main` references.
The validation job checks representative caller input and secret mappings in
[`tests/caller-contracts.json`](../tests/caller-contracts.json) against the
current `workflow_call` and composite action metadata. It catches removed
caller inputs and secrets, and new required inputs or secrets that would break
those callers.

The contracts capture key names only. They do not contain caller values or
secret values, and they do not execute build, release, signing, or publishing
jobs. When a caller's supported interface intentionally changes, update the
captured contract from the caller's workflow and review the change alongside
that caller migration. The current snapshot covers default-branch workflows in
[rbw](https://github.com/pschmitt/rbw),
[browser-daemon](https://github.com/pschmitt/browser-daemon),
[bruvtab](https://github.com/pschmitt/bruvtab),
[jollyfin](https://github.com/pschmitt/jollyfin),
[syncwich](https://github.com/pschmitt/syncwich), and
[stricknani](https://github.com/pschmitt/stricknani). Add a JSON entry for each
new representative call, using the workflow path and job or step path as its
`caller` and `context`; record the component filename, input categories, and
secret mapping shape. `with` values are recorded only by category (`string`,
`boolean`, `number`, or `expression`); expression values remain untyped. For
`secrets`, record explicit mapping names or `inherit`. A newly required secret
is flagged for inherited callers because the fixture cannot verify which
repository secrets exist. Keep representative callers from the different
workflow families in the fixture.
