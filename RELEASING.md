# Releasing

Releases are built and published by
[`.github/workflows/release.yml`](.github/workflows/release.yml) when a `v*` tag is pushed. PyPI
authenticates the workflow through
[trusted publishing](https://docs.pypi.org/trusted-publishers/), so no API token is stored in
GitHub.

## One-time setup

1. On PyPI, add a pending trusted publisher at
   <https://pypi.org/manage/account/publishing/> with:

   | Field | Value |
   |---|---|
   | PyPI project name | `rphonenumbers` |
   | Owner | `thevilledev` |
   | Repository name | `python-rlibphonenumber` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

   The first successful publish creates the project and turns the pending publisher into a
   regular one.

2. On GitHub, create an environment named `pypi` under Settings → Environments. Adding yourself
   as a required reviewer makes every publish wait for approval, and a deployment tag rule for
   `v*` keeps other refs from publishing.

## Cutting a release

1. Set the new version in `Cargo.toml`. It is the only place the version is defined: the wheel
   metadata and `rphonenumbers.__version__` are derived from it. Run `cargo check` so
   `Cargo.lock` picks up the new version; the release build uses `--locked` and fails otherwise.
2. In `CHANGELOG.md`, move the entries under `[Unreleased]` to a new `## [X.Y.Z] - YYYY-MM-DD`
   section and update the comparison links at the bottom.
3. Merge to `main`. To try the whole pipeline first, run the Release workflow from the Actions
   tab: a manual run builds and tests every wheel but does not publish.
4. Tag the merge commit and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

The workflow checks that the tag matches `Cargo.toml` and that `CHANGELOG.md` has a dated entry
for the version. It then builds the sdist and wheels, runs the test suite against the wheels on
each platform and, once the `pypi` environment is approved, uploads everything to PyPI with
[PEP 740](https://peps.python.org/pep-0740/) attestations.
