# Cargo-Grid

An MIT-licensed parametric Python/build123d generator for modular trunk and boot cargo mats. Python parameters own design intent; STEP is the primary CAD output. The CLI also produces checked STL meshes, core geometry 3MFs and unsliced Bambu-compatible jobs.

**Pre-release software.** Geometry checks, slicer interpretation and physical testing are separate gates. No fit, retention force, load rating, vehicle-service suitability or support-removal guarantee is implied.

## Install and run

Use Python 3.12 or newer with compatible build123d/OpenCascade wheels and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run cargo-grid --version
uv run cargo-grid --help
```

`python -m cargo_grid` is equivalent to the installed `cargo-grid` entry point. A built wheel can be installed into another Python environment; see [release checks](docs/release-checklist.md). No CAD-Pilot checkout, private reference, Bambu installation or network service is required to generate geometry.

The Python lock is machine-local and ignored. Use normal `uv sync` with your configured package feeds; do not commit registry credentials or machine-specific lock URLs.

## One-command workflows

Choose a new output directory for each job. All dimensions are millimeters, and `--build X Y Z` is required rather than guessing a printer.

### A tile or accessory

```sh
uv run cargo-grid part --build 150 150 50 --cells 2 1 --quantity 2 --output outputs/two-tiles
uv run cargo-grid part --build 150 150 80 --family plate --cells 1 1 --output outputs/x-plate
```

The first command requests **two 2x1 tiles**, not a 2x2 tile. At reference dimensions each is 126x66x13 mm. STEP/STL files represent each unique design once; the manifest and 3MF retain its quantity.

### An exact rectangular footprint

```sh
uv run cargo-grid layout --build 150 150 50 --footprint 320 230 --filler balanced --output outputs/exact-floor
```

The interior retains full 60 mm pitch. Leftover dimensions become integrated edge/corner filler volume, never scaled cells. `--filler balanced`, `positive` or `negative` controls its distribution. Outside joins are terminated; retained internal interfaces stay at full pitch. The manifest records assembly frames separately from print placement.

### A complete bounded catalogue

```sh
uv run cargo-grid catalogue --build 246 246 120 --output outputs/catalogue
```

This enumerates every ordered tile size that fits the usable envelope, including non-square orientations, plus the supported finite accessory variants. Oversized accessories are omitted with explicit manifest reasons and a CLI warning; catalogue completeness does not mean ignoring the chosen build volume.

Supported accessory families are `edge-x`, `edge-y`, `corner-in`, `corner-out`, `plate`, `lock-90`, `lock-45`, `support`, `support-bit` and `support-end`. Plates and locks use X-plug interfaces; physical support rails/end pieces are a separate family, not a claim of an unmeasured latch to the mat. See [geometry and scope](docs/geometry.md).

Catalogue 3MF output packs bounding rectangles across virtual plates, with optional 90-degree rotation. `--part-gap` controls separation. Add `--bambu`, explicit material labels, `--nozzle` and `--layer-height` for native plate metadata. Bambu jobs are limited to 36 plates and fail before export if packing exceeds that limit. The core format has no Bambu plate-limit claim.

### Explicit repeating holes

```sh
uv run cargo-grid part --build 150 150 50 --cells 2 1 --holes --hole-diameter 10 --hole-scope full --output outputs/full-holes
```

Holes are **off by default**. Enabling them requires both `--holes` and a diameter. The default `interior` scope protects joining edges; explicit `full` uses half-pitch sites including retained edges/corners, excluding X-socket centres. A default 2x1 full-hole tile has 13 extra sites. Terminated/filler boundaries and other rejected placements are recorded, not silently drilled or scaled.

### Targeted PETG/PLA roof supports

```sh
uv run cargo-grid part --build 350 320 325 --margin 37 --cells 2 1 --quantity 2 --holes --hole-diameter 10 --hole-scope full --bambu --material "Model PETG" PETG "#778877" --material "Interface PLA" PLA "#dddddd" --nozzle 0.8 --layer-height 0.4 --roof-support --roof-top-gap 0 --roof-interface-layers 2 --roof-interface-spacing 0 --output outputs/roof-job
```

This is an **H2D-sized diagnostic example**, not an embedded factory profile. Select the actual printer, bed, filament and process presets in Bambu Studio and inspect the resulting paths.

Roof support is off by default and limited to original-style tile `part` or `layout` jobs. When enabled, `critical` coverage places two nominal 3 mm enforcers per retained female roof on **both west and south edges**; `--roof-coverage full` requests the complete roofs. A 2x1 tile has three roofs and six critical enforcers. Male edges are not targeted, and terminated female edges are skipped individually.

The enforcers are non-printing selection volumes; they do not change tile STEP geometry. At reference dimensions they span Z=9.2--11.2 around the Z=10.2 ceiling so the first roof contacts remain selectable across the checked fine/coarse layer profiles. Printed support may extend beyond the nominal masks and temporarily occupy round edge cutouts. Check underside access and actual interfaces after every profile change.

The intentional PETG-base/PLA-interface roof workflow defaults to **zero top-contact distance, synchronized support/model layers, zero top-interface spacing and two top interface layers**. All five contact/process invariants, including build-plate-only off, are marked for preservation through profile changes. A positive `--roof-top-gap` explicitly selects a gapped workflow instead. Zero contact requires a dense interface with at least two layers; incompatible requests fail rather than silently falling back.

Zero contact is **not a generic support default or a chemical-compatibility guarantee**. The exporter requires declared PETG model/base and distinct PLA interface roles; it rejects same-material roof requests. This workflow also preserves 0.40 mm support/object XY distance: a bounded comparison removed small unintended PLA-interface/side-wall contacts while retaining vertical contact and all critical lips, with at most 1.44 percentage points less south-mask coverage. Positive-gap and general support workflows are unchanged. Verify the actual spools and profiles; an unverified substitution may fuse the support to the part.

Logical PETG model/base slot 1 and PLA interface slot 2 remain explicit. **Every generated Bambu plate defaults to automatic Convenience Mode** (`Auto For Match`), without a requested physical nozzle map or cached assignment. This is Cargo-Grid's preference, not a claim about Bambu's factory default. **Filament-Saving Mode** is `Auto For Flush`; **Custom** is `Manual` grouping. These modes are distinct from a customized process preset and from `normal(manual)` support selection. Convenience depends on the slicer's available filament information; inspect its actual assignment. Prime/flush behavior, foot expansion, thresholds, bridge detection, cooling and speeds are not changed by the zero-contact request.

With full holes and roof support on a 2x1 tile, the three female-edge round cutouts at `(0,30)`, `(30,0)` and `(90,0)` intentionally contain removable support during printing. Clear them from the underside after printing; this is not permanent CAD infill. The protected X openings remain clear in the checked paths. Do not assume every round hole is open while supports are present.

`--roof-nozzles 2 1` is an optional explicit Custom mapping. Otherwise no physical assignment is locked. **On build plate only is off.** Initial support-foot expansion uses the native automatic default; `--roof-foot-expansion 0` is an optional smaller-foot choice, while omission or `-1` leaves native automatic behavior. It is not a universal requirement for X-socket clearance. Default mapping/foot settings are not marked as overrides; explicit contact settings are retained through GUI import.

### Stacked identical tiles

```sh
uv run cargo-grid part --build 150 150 70 --cells 1 1 --quantity 4 --bambu --material "Model PETG" PETG "#778877" --material "Release PLA" PLA "#dddddd" --nozzle 0.4 --layer-height 0.2 --stack-count 2 --stack-gap 1 --interface-thickness 0.2 --material-roles 1 1 2 --output outputs/stack-job
```

Stacks use explicit sacrificial base and lower/upper release volumes between identical tiles. Quantities and partial batches are retained; `--stack-count auto` computes a bound from the usable height. These are geometry-based separation requests, not proven detachable prints.

**Roof supports and stacked separators cannot be combined.** Mixed catalogue stacking and catalogue/accessory roof support are also rejected. Do not infer support for those combinations from independent feature availability.

## Outputs and limits

Each successful job contains:

- One checked `.step` per unique design, with optional `.stl` files (`--no-stl` suppresses them).
- `job.3mf`: core geometry by default, or an unsliced native-compatible project with `--bambu`.
- `manifest.json`: schema and generator versions, design modes, resolved parameters, quantities, assembly frames, actual bounds, geometry/export checks, rejected/omitted entries and unsupported combinations.

Filenames include a hash of resolved design parameters. Existing non-empty job directories, standalone 3MF files and comparison reports are not overwritten. Invalid combinations are rejected before job files are written; a later CAD or I/O failure can leave diagnostic partial output, which should be inspected and retried in a new directory.

`--margin`, `--reserve` and repeatable `--exclude X Y WIDTH DEPTH` constrain the usable print envelope. They do not automatically know every printer's purge tower, brim, toolhead reach or sequential-print keep-outs. Inspect those using the selected slicer.

Core 3MF is geometry, not a multi-plate slicer configuration. Native output contains plate/material/modifier metadata but deliberately uses diagnostic printer/process IDs. It does **not** contain calibrated system profiles, sliced G-code or a printable job guarantee. Cargo-Grid does not invoke a slicer, connect to a printer, send files to hardware or start prints.

## Python API

```python
from pathlib import Path

from cargo_grid import BuildVolume, Tile, make_tile
from cargo_grid.export import export_job
from cargo_grid.jobs import Job, tile_design

shape = make_tile(Tile(nx=2, ny=1))
design = tile_design(Tile(nx=2, ny=1, hole_diameter=10, hole_scope="full"))
design.quantity = 2
export_job(Job([design], BuildVolume(150, 150, 50), "part"), Path("outputs/python-job"))
```

`Interface`, `Tile` and `BuildVolume` describe geometry and usable space. `exact_layout`/`layout_job` build exact-footprint jobs; `catalogue_job` enumerates the bounded library. `BambuSettings`/`Material`, `RoofSupportSettings` and `StackSettings` describe optional export requests. `RoofSupportSettings()` explicitly requests the maintained PETG/PLA zero-contact workflow: gap 0, two dense interface layers and synchronized layer heights. A positive gap selects gapped contact. Its nozzle map and foot expansion default to `None`. Geometry functions do not read reference meshes or printer profiles.

`examples/tile.py` and `examples/coupons.py` expose `gen_step()` for a separate CAD workbench. Run that workbench from the design root with this package importable, generate an explicit project-relative STEP path, and inspect the same file. Workbench tools/viewers are external, not bundled or installed by Cargo-Grid.

## Compatibility and provenance

The default **original** joint style preserves the independently measured functional datums: 60 mm pitch, 13 mm tile height, partial-height male joins, roofed female pockets and the shared X attachment interface. Reference-dimension compatibility is a geometric intent, not a printed-friction or load guarantee.

`--joint-style full-height` remains explicitly **experimental**. At reference dimensions its negative-X pocket/socket web becomes very thin near the top and opens to the exterior; it is not a structural recommendation. Full-height male tabs do not fit original roofed female pockets. Changing pitch, height or fit offset also changes compatibility assumptions.

The project was informed by functional measurements of [Tora.'s trunk organizer mat](https://makerworld.com/en/models/2822185-trunk-organizer-mat#profileId-3143201). Its files have separate restrictive terms. **No reference meshes, decorative contours, private files or workbench code are distributed here.** The MIT license covers this independently authored code, not third-party assets or a blanket clearance of design rights.

If you lawfully hold a local reference, optional comparison is explicit and offline:

```sh
uv run cargo-grid compare-reference path/to/reference.3mf --output outputs/reference-comparison.json
```

That comparison checks original-style functional geometry; it is not a license assessment or a physical test. Keep external references and generated artifacts out of source releases.

## Development

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -m "not native and not reference"
uv build
uv run python tools/check_distributions.py dist
```

Portable CI uses Python 3.12 and does not need a private reference or Bambu Studio. Native and reference tests are opt-in through `CARGO_GRID_BAMBU` and `CARGO_GRID_REFERENCE`; unset them to keep those checks skipped. See the [release checklist](docs/release-checklist.md) for installed-wheel and external CAD checks, tracked-source release preparation and remaining physical gates.

There is no browser generator/button yet; the CLI provides the one-command workflows. Physical fit, detachment, flatness, service loads and environmental performance remain unverified until applicable observations are supplied and recorded.
