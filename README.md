# Cargo-Grid

**Your space. Your grid.** Generate a modular cargo mat in the size you need, add the pieces that suit your load, and keep the design editable in Python.

![Two real isometric 2x1 tiles: original joining geometry without optional holes on the left, and the optional 13-hole pattern on the right.](docs/images/hero.png)

*Actual STEP-derived renders from this generator, not reference meshes or concept art. Both tiles use the original joint style and nominal 60 mm pitch; the optional holes remove material and need their own fit, strength and support checks.*

Cargo-Grid is an independently authored, MIT-licensed Python/build123d tool. It creates STEP, STL and 3MF files—not a locked set of one-size models. **Pre-release:** geometric compatibility is a design intent, not a certification of printed fit or load capacity.

## Your first 2x1 tile in three steps

You need Python 3.12 or newer with compatible CAD wheels, plus uv. No CAD workbench, Bambu installation, private reference or PyPI publication is required for source use.

### 1. Get the source

Clone this repository or use GitHub's **Code / Download ZIP**, then open a terminal in the extracted repository folder.

### 2. Install the local environment

```sh
uv sync
```

### 3. Generate a real tile

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --cells 2 1 --output outputs/first-tile
```

That creates one **2x1 tile**, nominally **126x66x13 mm**, using original roofed joints and no optional holes. Look in `outputs/first-tile`: the named STEP is your primary CAD file, the STL is a checked mesh, `job.3mf` carries geometry, and `manifest.json` explains what was generated.

The three required build dimensions describe the printer, not the tile: `--build-width-mm` is X/left-right, `--build-depth-mm` is Y/front-back, and `--build-height-mm` is Z/maximum print height. All are millimeters with no assumed defaults. Replace the example values with your printer's limits, then inspect the result in your slicer. Use a new output directory for each job; existing jobs are not overwritten.

## Start simple. Add only what you need.

**Keep the original interface.** Default tiles retain the measured joining datums and shared X attachment interface. Printed friction and retention still depend on your machine, material and process.

**Open up the pattern.** Optional round holes can cover only the interior or extend across retained edges and corners. The illustrated 2x1 full pattern has 13 additional 10 mm holes:

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --cells 2 1 --holes --hole-diameter 10 --hole-scope full --output outputs/open-pattern
```

**Fit a rectangle exactly.** Keep full-pitch cells in the middle and fill leftover dimensions with integrated edge/corner material—not stretched cells:

```sh
uv run cargo-grid layout --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --footprint 320 230 --filler balanced --output outputs/exact-floor
```

**Make two, not a bigger one.** Add `--quantity 2` to a 2x1 part job. Each unique design gets one STEP/STL; quantities and placements are retained in the manifest and 3MF.

## A parts drawer, not just a floor tile

Use plates and upright stops to add attachment surfaces, edge/corner pieces to finish a run, and the separate rail/connector family where your design needs physical support members. Those rails are not slicer-generated supports and do not imply an unmeasured latch to the mat.

![All eleven X-plug attachment variants: three plates, six right-angle stops and two angled stops, each individually labeled.](docs/images/x-attachments.png)

The complete library contains **44 accessory variants** for the documented **350x320x325 mm catalogue envelope**, original joints and default accessory parameters. **[Browse all 44 parts, each with its own thumbnail beside its name, dimensions and purpose](docs/attachments.md).** The inventory is grouped by family: plates, upright/angled stops, edge strips, inner/outer corners, support rails, rail ends and connectors.

*Every inventory row has a unique actual STEP-derived render and matching alt text. Camera and background are consistent; physical scale is shared within a family, not between families. The overview above is a quick introduction, not a substitute for the individual pictures. Colors are illustrative. Other build envelopes, lengths and heights can produce additional parametric variants beyond this bounded catalogue.*

Generate the whole bounded catalogue in one command:

```sh
uv run cargo-grid catalogue --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --output outputs/catalogue
```

It includes every ordered tile size that fits and the supported accessory variants. Oversized accessories are listed as omitted rather than shrunk. You can also request one piece, for example:

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 80 --family plate --cells 1 1 --output outputs/x-plate
```

## Support the roofs without changing the mat

### The problem: a small ceiling over each receiving joint

A **roof** is the thin ceiling above a female joining pocket on the tile's west or south edge. It has open space below it, so its first printed layer needs a temporary foundation to avoid sagging or curling. A 2x1 tile has three such roofs. Cargo-Grid marks those areas for removable support without changing the mat itself.

Use this workflow when printing a **PETG tile with a separate PLA interface on a two-material, two-nozzle setup**. The **interface** is the dense top layer of support that touches the roof; the support below it stays PETG. PLA and PETG are different polymers, which makes a touching, zero-air-gap interface a useful separation strategy for the intended pair. This is not a guarantee for every product or additive: verify your actual spools, and never reuse zero gap with same-material support or an unverified substitute that could fuse.

### Generate the two-tile support job

This copy-paste example requests two full-hole 2x1 tiles and an H2D-sized build envelope. Change the three build dimensions and the nozzle/layer values if your setup differs; the example does not detect or calibrate hardware.

```sh
uv run cargo-grid part --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --margin 37 --cells 2 1 --quantity 2 --holes --hole-diameter 10 --hole-scope full --bambu --material "Model PETG" PETG "#778877" --material "Interface PLA" PLA "#dddddd" --nozzle 0.8 --layer-height 0.32 --roof-support --output outputs/roof-job
```

Open **`outputs/roof-job/job.3mf` as a complete project** in Bambu Studio, not as imported geometry. It is an unsliced diagnostic project with two plates, not a ready-to-print factory profile. Select the actual printer, process, bed and PETG/PLA profiles. The same folder also contains the tile's STEP/STL and `manifest.json`.

### What Cargo-Grid sets for this workflow

Support is enabled under the marked west/south roofs, with PETG in logical slot 1 for the model/support base and PLA in slot 2 for the interface. Six guarded settings are preserved when process profiles change:

| Setting | What it means |
| --- | --- |
| Top contact distance: **0 mm** | No deliberate empty air layer between the PLA interface and roof bottom. |
| Independent support layer height: **off** | Support and model follow the same layer schedule. |
| Top interface spacing: **0 mm** | Request a dense supporting surface, not sparse lines. |
| Top interface layers: **2 by default** | Keep at least two dense PLA layers below each roof. |
| On build plate only: **off** | Do not discard needed support merely because of that filter. |
| Support/object XY distance: **0.40 mm** | Keep lateral clearance from pocket walls while the interface touches the roof vertically. |

Every plate uses automatic **Convenience Mode** (`Auto For Match`); no physical nozzle assignment is locked. Initial support-foot expansion remains automatic. Cargo-Grid does not alter cooling, speeds, bridge thresholds or prime/flush behavior for this contact request.

### Check the preview before printing

1. Confirm the active printer/nozzles, PETG model/base and PLA interface assignments. Slice the project; an enabled Support checkbox alone is not proof that supports were generated.
2. Inspect each west/south pocket in layer view or from below. The final PLA interface surface must directly meet the **bottom** of the first roof layer, with no empty layer. Their nozzle Z values need not match: a layer has thickness. At the checked 0.32 mm schedule, interface top and roof bottom meet at Z=10.32 while the first roof is extruded at Z=10.64.
3. Confirm the protected X-shaped openings are clear and all three roofs retain support on both sides of their round cutout. On this full-hole 2x1 job, the round edge holes at **(0,30), (30,0) and (90,0) are intentionally not open during printing**: they contain removable support. Do not confuse them with blocked X openings or permanent CAD infill.
4. Check for unwanted support touching pocket side walls, an out-of-bounds prime tower or new warnings. Inspect both plates and recheck after any profile/material change. Do not start a print with missing contacts or an unexplained material assignment.

### After printing

Let the part cool according to the material/bed guidance. Reach the support from the open underside and corresponding female edge, remove it, and clear the three temporary support-filled round cutouts before assembly. Check for remaining PLA, damaged roof lips, local curl and excessive joining force. Removal access does not prove easy or damage-free separation.

The settings have geometry and headless toolpath evidence; **corrected physical roof finish, release force, long-term fit and strength are not yet verified**. Record the actual nozzle, layer height, materials and observations rather than assuming one trial validates every profile. Advanced contact, coverage and stacking options follow below.

## Advanced reference

The simple commands above use the same maintained CLI/API as the more explicit workflows below. `python -m cargo_grid` is equivalent to the installed `cargo-grid` entry point.

<details>
<summary><strong>Commands, export formats and usable build space</strong></summary>

```sh
uv run cargo-grid --help
uv run cargo-grid part --help
uv run cargo-grid layout --help
uv run cargo-grid catalogue --help
uv run cargo-grid compare-reference --help
```

`part` creates one design with a quantity; `layout` creates an exact rectangular assembly; `catalogue` enumerates the bounded library; `compare-reference` performs an explicit local comparison against a lawful compatible reference archive. No reference is downloaded or uploaded by the generator.

`--build-width-mm`, `--build-depth-mm` and `--build-height-mm` are all required positive finite dimensions in millimeters: X/left-right, Y/front-back and Z/maximum print height. `--height` is different: it changes the tile model height. The manifest retains its existing `build.x`, `build.y` and `build.z` fields in millimeters, corresponding to the three named CLI options.

`--margin MM` insets each X/Y side; `--reserve X_MM Y_MM Z_MM` withholds additional space at the positive X/Y edges and top Z. Repeatable `--exclude X_MM Y_MM WIDTH_MM DEPTH_MM` removes a rectangular plate area by its lower-left X/Y and width/depth. These inputs do not know every printer's prime tower, brim, toolhead reach or sequential-print keep-outs; inspect those in your slicer.

`--filler balanced`, `positive` and `negative` control leftover layout material. Assembly frames describe the floor arrangement; print placement is separate. `--part-gap` controls catalogue packing separation. Native jobs are limited to 36 plates; an over-capacity job fails before export.

Outputs are one checked STEP and optional STL per unique design, `job.3mf`, and a versioned `manifest.json` with parameters, modes, quantities, assembly frames, actual bounds, validation results and omitted/rejected entries. `--no-stl` suppresses STL output. Filenames include parameter hashes.

Core 3MF is geometry, not a multi-plate print configuration. `--bambu` adds native-compatible plate/material/modifier metadata with **diagnostic**, unsliced profile IDs. It does not embed calibrated factory profiles or produce G-code. Existing non-empty output directories, standalone 3MFs and comparison reports are not overwritten; a later CAD/I/O failure can leave diagnostic partial output to inspect before retrying in a new directory.

</details>

<details>
<summary><strong>Original joints, optional holes and compatibility limits</strong></summary>

Original roofed joints are the default. The reference datums are 60 mm pitch and 13 mm height, with male ledges at Z=10 and female ceilings at Z=10.2. An unterminated tile measures `(60*nx+6, 60*ny+6, 13)` at those settings. Changing pitch, height or fit offset changes compatibility assumptions; it is not calibrated shrink compensation.

`--joint-style full-height` is explicitly experimental. Its open pockets leave a very thin negative-X pocket/socket web near the top and can open to the exterior. It is not a structural recommendation, and its male tabs do not fit original roofed female pockets.

Holes are off by default. CLI use requires both `--holes` and `--hole-diameter`; `interior` is the default scope. Explicit `full` uses half-pitch sites including retained edges/corners, excluding X centres. Terminated/filler boundaries and keep-outs can reject sites; the manifest records why.

Read the [geometry contract](docs/geometry.md) before changing interfaces or validation budgets.

</details>

<details>
<summary><strong>Explicit roof-support and identical-tile stack workflows</strong></summary>

Roof support is off by default and limited to original-style tile `part`/`layout` jobs. The [beginner workflow](#support-the-roofs-without-changing-the-mat) provides the complete command and preview/removal checks. `--roof-coverage critical` is the enabled default; `full` requests whole-roof coverage. At reference dimensions, selection volumes span Z=9.2 to 11.2 around the Z=10.2 roof to cover multiple layer schedules.

`--roof-top-gap` defaults to 0 for the intentional PETG/PLA workflow; a positive value selects gapped contact. `--roof-interface-layers` defaults to 2 and `--roof-interface-spacing` to 0; zero contact requires a dense interface and at least two layers.

The zero-contact workflow marks all five contact invariants plus its scoped 0.40 mm XY safeguard against profile resets. It does not change model geometry, masks, prime/flush behavior, thresholds, bridge detection, cooling or speeds. Positive-gap and general support behavior remain separate.

Convenience Mode is `Auto For Match`; Filament-Saving Mode is `Auto For Flush`; Custom grouping is `Manual`. These are distinct from the `normal(manual)` support type. `--roof-nozzles 2 1` requests Custom physical assignment explicitly. `--roof-foot-expansion 0` selects a smaller support foot; omission or `-1` leaves native automatic expansion. An automatically chosen nozzle map is not a locked contract.

Stacks use explicit sacrificial base and lower/upper release volumes between repeated identical tiles:

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 70 --cells 1 1 --quantity 4 --bambu --material "Model PETG" PETG "#778877" --material "Release PLA" PLA "#dddddd" --nozzle 0.4 --layer-height 0.2 --stack-count 2 --stack-gap 1 --interface-thickness 0.2 --material-roles 1 1 2 --output outputs/stack-job
```

`--stack-count auto` computes a bound from usable height; partial quantities are retained. **Roof supports cannot be combined with stacks.** Mixed catalogue stacking and catalogue/accessory roof support remain unsupported. Separation geometry is not a guarantee of successful physical detachment.

</details>

<details>
<summary><strong>Python API, development and documentation regeneration</strong></summary>

```python
from pathlib import Path
from cargo_grid import BuildVolume, Tile, make_tile
from cargo_grid.export import export_job
from cargo_grid.jobs import Job, tile_design

shape = make_tile(Tile(nx=2, ny=1))
design = tile_design(Tile(nx=2, ny=1, hole_diameter=10, hole_scope="full"))
export_job(Job([design], BuildVolume(150, 150, 50), "part"), Path("outputs/python-job"))
```

`Interface`, `Tile` and `BuildVolume` own geometry/space parameters. `exact_layout`/`layout_job` and `catalogue_job` create the larger workflows. `BambuSettings`/`Material`, `RoofSupportSettings` and `StackSettings` describe optional export requests. `RoofSupportSettings()` selects the guarded PETG/PLA zero-contact defaults; same-material/unsupported roof pairs are rejected.

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -m "not native and not reference"
uv build
uv run python tools/check_distributions.py dist
```

Use configured feeds and keep `uv.lock` local/ignored. Native/reference tests are optional through explicitly supplied `CARGO_GRID_BAMBU` and `CARGO_GRID_REFERENCE`; they remain skips when unavailable. See [repository instructions](AGENTS.md), [release checks](docs/release-checklist.md) and [gallery reproduction](docs/attachments.md#reproduce-the-images).

Documentation images are the narrow, intentional exception to ignored generated outputs. Raw STEP/render intermediates, environments, study data and private references do not belong in source releases. Rendering uses external workbench tooling, not new runtime dependencies.

</details>

## Open source, with clear boundaries

[The MIT license](LICENSE) covers this independently authored code. Functional measurements of Tora.'s MakerWorld trunk-organizer mat informed the interfaces; that reference has separate restrictive terms. No reference meshes, decorative assets, private files, slicer profiles or workbench code are bundled, and fresh source code does not establish blanket rights over another design.

Python parameters are the editable design; STEP, meshes and images are derived. Cargo-Grid does not connect to a printer, operate the GUI, start prints or certify physical fit, retention, strength or service conditions. There is no browser generator/button yet—the CLI provides the one-command workflows.
