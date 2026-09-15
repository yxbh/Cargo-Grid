# Release checks

These are repeatable maintainer gates, not authorization to publish, operate a printer or claim physical compatibility.

## Source and environment

- Review the intended source changes and license/provenance boundaries. Preserve the repository's MIT notice and any separately licensed dependencies.
- Use Python 3.12 or newer with compatible CAD wheels. Run normal `uv sync --group dev` with the configured feeds. Keep `uv.lock`, environments, runtime files and generated output local.
- Confirm that the source version in `src/cargo_grid/_version.py` is the intended pre-release or release identifier. The package, CLI and manifest derive their version from it.

## Portable checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -m "not native and not reference"
git diff --check
uv build
uv run python tools/check_distributions.py dist
```

Use a fresh distribution output directory when old builds are present; the archive checker intentionally rejects ambiguous collections of wheels/source archives. It verifies metadata, entry points, license preservation and the exclusion of generated/runtime artifacts. It is not a comprehensive secret or license scanner.

Install the emitted wheel into a fresh environment, outside the source import path. Check both `python -m cargo_grid --version` and the `cargo-grid --help` entry point, then generate a small part and independently reimport its STEP to confirm one valid positive-volume solid and the expected dimensions. Do not mistake an editable source import for a wheel-install test.

CI performs the portable tests, distribution checks and an installed-wheel CLI generation smoke. It does not access private references, system slicer profiles or hardware.

## Optional native and reference checks

Set `CARGO_GRID_BAMBU` to an explicitly chosen local Bambu Studio executable and `CARGO_GRID_REFERENCE` to a lawful local reference file, then run:

```sh
uv run pytest -q
```

The tests still skip unavailable external checks. Native CLI import/export is not GUI slicing or printing. If changing Bambu settings or modifier behavior, inspect an actual GUI-generated slice under the intended profile: logical material roles, automatic versus explicitly Custom nozzle grouping, every requested support contact, X-socket clearance, actual model/support extrusion separation and prime-tower reach. Preserve the selected profile and evidence with ignored project outputs, not in package contents.

If using a separate CAD workbench, use its current documented interpreter and launchers from this design root. Generate `examples/tile.py` to a fresh project-relative STEP, inspect that same STEP, and open it in an available viewer. Prefer a maintained CAD canvas only when it is actually registered; otherwise use that workbench's documented fallback. Record the toolchain revision and resolved dependency versions with the local evidence when reproduction requires them. Do not copy the workbench into this repository.

## Physical and compatibility gates

- Original/default versus experimental full-height geometry must remain explicit. A warning-free slice does not remove the known full-height thin-web limitation.
- Holes and roof support remain off by default. Full hole scope, support contacts and stacked separators require their explicit options.
- Roof support covers retained west/south female edges only; roof-plus-stack and mixed-catalogue combinations remain rejected.
- Native default filament grouping and support-foot expansion are not fixed physical nozzle assignments or calibrated adhesion settings. Recheck actual paths after profile changes.
- Record physical fit, roof-support removal, finish, flatness and both-direction joining observations with the actual printer/material/profile. Do not extrapolate one trial to all profiles, climates or loads.

## Preparing an authorized release

Local builds made during development are verification artifacts, not published releases. After the maintainer has separately reviewed and committed the source, prepare release input from tracked files at the reviewed revision, for example with `git archive`, rather than zipping the working directory. Check the tracked file inventory before archiving, then build and inspect distributions from the extracted reviewed source.

Do not include local locks, reference meshes, system profile JSON, `.venv`, `.local`, study outputs, G-code, screenshots or runtime diagnostics. Publication, tags and pushes remain separate explicit maintainer decisions; this checklist does not perform them.
