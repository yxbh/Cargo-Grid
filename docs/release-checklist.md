# Release checklist

Use this before cutting a release. These checks cover the source and packages. They don't publish anything or prove that a printed part fits.

## Set up the checkout

1. Review the source changes, version and licence boundary.
2. Run `uv sync --group dev` with the configured package feeds.
3. Keep `uv.lock`, virtual environments, caches and generated jobs out of the commit.
4. Confirm `src/cargo_grid/_version.py` has the intended version.

## Run the portable checks

The documented workstation uses 12 process workers for the full portable suite. Use fewer on a smaller machine:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -n 12 --dist loadfile -m "not native and not reference"
git diff --check
uv build
uv run python tools/check_distributions.py dist
```

Use fewer workers on a smaller machine. CI uses two workers on the GitHub runner. Do not use xdist for native Bambu or local-reference tests.

Build into a fresh directory. The distribution checker expects one wheel and one source archive and rejects extra build output. It checks package metadata, entry points, the licence and the allowlist; it isn't a general secret or licence scanner.

Install the wheel into a clean Python 3.12 environment outside the source path. Check `python -m cargo_grid --version`, `cargo-grid --help` and at least one generated part. Reimport its STEP and check that it is one valid, positive-volume solid with the expected size.

## What CI checks

CI runs for pull requests, pushes to `main` and manual dispatches. It does not run a second copy for every push to a PR branch. A concurrency group cancels older runs when a newer commit reaches the same PR.

The Linux job installs the CAD runtime libraries, runs Ruff, runs the portable tests with two process workers, builds both distributions and installs the wheel into a clean environment. Its smoke commands generate a tile, bracket, normal stop and ramp, then check their manifest dimensions, orientations and support settings with named assertion messages.

The portable test command includes pytest's built-in `--durations=0 --durations-min=0` report. It lists every test's setup, call and teardown durations, slowest first, without adding a timing plugin. Add the same flags to a local run when investigating slow tests. These are per-phase elapsed times: phases on parallel workers can overlap, so their sum is not the CI job's wall time.

CI can't use private reference files, local slicer profiles or printers. Treat a CI failure as a source, package or test failure until the log shows otherwise.

## Optional local Bambu and reference checks

Normal generation does not need either resource. To include the optional checks, point `CARGO_GRID_BAMBU` at the chosen Bambu Studio CLI and optionally point `CARGO_GRID_REFERENCE` at a local reference 3MF, then run the suite serially:

```sh
uv run pytest -q
```

Unavailable checks skip. `cargo-grid compare-reference --reference-file path/to/reference.3mf --output outputs/reference-report.json` runs the same local interface comparison without uploading the file.

Native CLI import/export isn't a print test. When Bambu settings or modifiers change, slice the affected job with the intended machine, process and materials. Check material roles, nozzle mapping, support contact, X-socket clearance, model/support paths and tower reach. Keep profiles, G-code and logs in ignored output directories.

If a separate CAD workbench is needed, use its documented interpreter and launchers from this repository root. Generate a fresh project-relative STEP, inspect that same file and record the workbench revision with the local evidence. Do not copy workbench files into this repository.

## Check the physical assumptions

- Keep original roofed joints and experimental open-through tile-edge joints clearly separated.
- Confirm the default full 10 mm hole pattern or a `--no-holes` opt-out; roof support remains opt-in.
- Confirm roof support appears only under retained west/south female roofs.
- Recheck support, brim and tower paths after profile changes.
- Record printer, nozzle, layer height, materials, fit, roof finish, support removal and flatness for any physical trial.

One print doesn't establish fit or strength for every profile, material, climate or load.

## Prepare release source

After the release commit has been reviewed, create the release input from tracked files at that revision, for example with `git archive`. Do not zip the working directory.

Exclude local locks, environments, caches, reference meshes, system profiles, G-code, study output and runtime diagnostics. The maintained documentation images are the exception: six overview images, 161 accessory thumbnails and their provenance manifest. The source archive contains exactly 167 PNGs; the runtime wheel contains none. A partial image update keeps the source and tool revisions for retained images and records separate provenance for regenerated images.

Run `tools/render_docs.py --check` to confirm image hashes, links and one-to-one inventory coverage. Tagging, uploading packages/models and merging remain separate maintainer actions.
