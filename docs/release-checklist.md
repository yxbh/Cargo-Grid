# Release checks

Use this checklist before cutting a release. It checks the source and packages; it does not publish anything or prove that a printed part fits.

## Set up the checkout

1. Review the source changes, version and license boundary.
2. Run `uv sync --group dev` with the configured package feeds.
3. Keep `uv.lock`, virtual environments, caches and generated jobs out of the commit.
4. Confirm `src/cargo_grid/_version.py` has the intended version.

## Run the portable checks

On the documented local workstation, four process workers were slightly faster than eight for a representative CAD/CLI set because `--dist loadfile` had only five files to schedule. Use:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -n 12 --dist loadfile -m "not native and not reference"
git diff --check
uv build
uv run python tools/check_distributions.py dist
```

Use fewer workers on a smaller machine. CI uses two workers on the GitHub runner. Do not use xdist for native Bambu or local-reference tests.

Build into a fresh directory. The distribution checker expects one wheel and one source archive and rejects extra build output. It checks package metadata, entry points, the license and the allowlist; it is not a general secret or license scanner.

Install the wheel into a clean Python 3.12 environment outside the source path. Check `python -m cargo_grid --version`, `cargo-grid --help` and at least one generated part. Reimport its STEP and check that it is one valid, positive-volume solid with the expected size.

## What CI checks

CI runs for pull requests, pushes to `main` and manual dispatches. It does not run a second copy for every push to a PR branch. A concurrency group cancels older runs when a newer commit reaches the same PR.

The Linux job installs the CAD runtime libraries, runs Ruff, runs the portable tests with two process workers, builds both distributions and installs the wheel into a clean environment. Its smoke commands generate a tile, bracket, normal stop and ramp, then check their manifest dimensions, orientations and support settings with named assertion messages.

CI cannot use private reference files, local slicer profiles or printers. A CI failure is a source/package/test failure until the log shows otherwise; do not label it infrastructure noise without evidence.

## Optional local Bambu and reference checks

Normal generation does not need either resource. To include the optional checks, point `CARGO_GRID_BAMBU` at the chosen Bambu Studio CLI and optionally point `CARGO_GRID_REFERENCE` at a local reference 3MF, then run the suite serially:

```sh
uv run pytest -q
```

Unavailable checks skip. `cargo-grid compare-reference --reference-file path/to/reference.3mf --output outputs/reference-report.json` runs the same local interface comparison without uploading the file.

Native CLI import/export is not a print test. When Bambu settings or modifier behavior changes, slice the affected job with the intended machine, process and material profiles. Check material roles, nozzle mapping, support contact, X-socket clearance, model/support paths and tower reach. Keep profiles, G-code and logs in ignored output directories.

If a separate CAD workbench is needed, use its documented interpreter and launchers from this repository root. Generate a fresh project-relative STEP, inspect that same file and record the workbench revision with the local evidence. Do not copy workbench files into this repository.

## Check the physical assumptions

- Keep original joints and experimental full-height joints clearly separated.
- Leave holes and roof support off unless the job asks for them.
- Confirm roof support appears only under retained west/south female roofs.
- Recheck support, brim and tower paths after profile changes.
- Record printer, nozzle, layer height, materials, fit, roof finish, support removal and flatness for any physical trial.

One print does not establish fit or strength for every profile, material, climate or load.

## Prepare release source

After the release commit has been reviewed, create the release input from tracked files at that revision, for example with `git archive`. Do not zip the working directory.

Exclude local locks, environments, caches, reference meshes, system profiles, G-code, study output and runtime diagnostics. The maintained documentation images are the exception: five overview images, 56 accessory thumbnails and their provenance manifest. The source archive contains exactly 61 PNGs; the runtime wheel contains none.

Run `tools/render_docs.py --check` to confirm image hashes, links and one-to-one inventory coverage. Tagging, uploading packages/models and merging remain separate maintainer actions.
