# Cargo-Grid

Cargo-Grid generates modular cargo-mat tiles and accessories from Python. Defaults are 60 mm units, 13 mm tile thickness and the full 10 mm round-hole pattern. You can export STEP, STL and editable 3MF files for one part, a fitted rectangular layout or the complete catalogue.

![The default full-hole 4x4 tile beside the explicit no-hole version.](docs/images/hero.png)

This is an independently authored, MIT-licensed pre-release. The geometry and export checks catch CAD and file errors, but printed fit, support removal and load capacity still need testing on your machine and material.

## Make a 2x1 tile

Install `uv`, clone or download this repository, then run these commands from the repository folder:

```sh
uv sync
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --width-cells 2 --depth-cells 1 --output outputs/first-tile
```

The result is a nominal 126x66x13 mm tile with the original roofed joints and all 13 available 10 mm holes. `outputs/first-tile` contains:

- a named STEP file for CAD work;
- an STL mesh;
- `job.3mf`;
- `manifest.json`, which records dimensions, quantities, placement and validation results.

The three build dimensions describe available printer space in millimeters: width is X/left-right, depth is Y/front-back and height is Z. Change them to suit your printer. Cargo-Grid refuses to overwrite an existing output directory, so use a new name for each run.

## Choose the tile size and pattern

`--width-cells` and `--depth-cells` set the tile grid. Add `--copy-count 2` when you want two copies of the same part rather than one larger tile.

Full 10 mm round holes are the default, including retained edge and corner sites. Use `--no-holes` for solid webs:

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --width-cells 2 --depth-cells 1 --no-holes --output outputs/solid-pattern
```

`--holes` remains an explicit positive alias. Use `--hole-diameter-mm` to change 10 mm or `--hole-scope interior` when you only want complete interior holes. X attachment centres and other protected interfaces are never drilled. At small unit sizes, keep-outs can reject every requested hole; the CLI then suggests a smaller diameter or `--no-holes`.

Unit size and tile thickness are independent. This example keeps the 13 mm thickness while changing cells and matching local-plane interfaces to 30 mm:

```sh
uv run cargo-grid part --unit-size-mm 30 --tile-thickness-mm 13 --build-width-mm 100 --build-depth-mm 100 --build-height-mm 50 --no-holes --output outputs/30mm-unit
```

The standard 60/13 setting remains compatible with the documented stock geometry. Other values match parts generated with the same two settings, but are not claimed compatible with standard parts.

For a floor that must fill an exact rectangle, use `layout`. Full 60 mm cells stay in the middle and the leftover width/depth becomes integrated edge material:

```sh
uv run cargo-grid layout --build-width-mm 150 --build-depth-mm 150 --build-height-mm 50 --layout-width-mm 320 --layout-depth-mm 230 --filler-placement balanced --output outputs/exact-floor
```

## Browse and generate accessories

The 350x320x325 mm reference catalogue contains 56 accessories: ramps, attachment plates, five vertical tile brackets, eight normal stops, two angled stops, edge/corner pieces and separate support rails/connectors.

![Three plates, five tile brackets, eight normal stops and two angled stops that use the X attachment interface.](docs/images/x-attachments.png)

See the [complete illustrated attachment list](docs/attachments.md) for part names, dimensions and individual thumbnails.

Generate one accessory with `part`:

```sh
uv run cargo-grid part --family plate --width-cells 1 --depth-cells 1 --build-width-mm 150 --build-depth-mm 150 --build-height-mm 80 --output outputs/x-plate
```

For Bambu output, attachment plates are flipped X=180 degrees so the broad plate body starts on the bed and the X plugs grow upward. STEP, STL and core 3MF keep the source orientation.

Generate every tile and accessory that fits a build envelope with `catalogue`:

```sh
uv run cargo-grid catalogue --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --output outputs/catalogue
```

The manifest lists anything omitted because it did not fit.

## Make the full H2D catalogue

This command creates the documented 81-design H2D project: 25 tile sizes with the full 10 mm hole pattern and all 56 accessories.

```sh
uv run cargo-grid catalogue --h2d-dual-safe --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --bambu --material "Bambu PETG Basic @BBL H2D 0.8 nozzle" PETG "#637b70" --nozzle-diameter-mm 0.8 --layer-height-mm 0.32 --no-stl --output outputs/full-catalogue
```

Open `outputs/full-catalogue/job.3mf` as a project. It has 24 family-grouped plates. Common plates keep model bounds within the H2D shared reach (X=25..325, Y=0..320, Z<=320), add a 5 mm model inset and leave at least 10 mm between model bounds. The 306x306 mm 5x5 tile needs the wider left-nozzle area, so its plate is named `5x5 TILE - SINGLE NOZZLE ONLY - LEFT` and maps slot 1 to the left nozzle. Other plates keep automatic `Auto For Match` mapping.

The project names the H2D 0.8 nozzle, 0.32 mm Balanced Strength process, Textured PEI plate and Bambu PETG Basic profile. Confirm those profiles and your loaded filament before slicing. The catalogue does not add PLA roof interfaces to tiles; the PETG/PLA roof-support job below remains a separate tile-only workflow.

## Vertical tile brackets

A bracket holds a separate ordinary tile upright. Its underside-outward placement remains the default and the accepted posts also support a top-outward placement; solid backing makes covered round holes blind while assembled.

![Five brackets shown with separate floor and upright wall tiles.](docs/images/vertical-tile-brackets.png)

The part names state both footprints:

| Bracket | Floor base | Upright wall |
| --- | --- | --- |
| Deep tall | 1x2 | 1x2 |
| Wide low | 2x1 | 2x1 |
| Deep square | 2x2 | 2x2 |
| Shallow tall | 1x1 | 1x2 |
| Shallow wide | 2x1 | 2x2 |

For brackets, `--width-cells` sets the shared X width, `--depth-cells` sets floor depth and `--panel-height-cells` sets wall height. Omit panel height to match the floor depth.

```sh
uv run cargo-grid part --family vertical-tile-bracket --width-cells 1 --depth-cells 1 --panel-height-cells 2 --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --bambu --material "Model PETG" PETG "#637b70" --nozzle-diameter-mm 0.4 --layer-height-mm 0.2 --output outputs/shallow-tall-bracket
```

This exports the bracket only. Generate its 1x1 floor tile and 1x2 wall tile separately with the same unit size, tile thickness and fit offset.

The accepted wall posts remove the wide root flare, inset the straight stem profile by 0.08 mm and keep the final 2 mm rounded tip unchanged. The wall tile can face either way. The original underside-outward placement remains the default; for its top face outward, rotate the wall tile Z=180 degrees and then X=-90 degrees before placing it on the same post centers. Use the same orientation for every adjoining wall tile because top-outward placement reverses left/right joining handedness. CAD checks preserve the seated top-outward arrangement, but the unchanged tip still has a small nominal interference during a straight insertion sweep. Physical fit is pending the user's test print.

Bambu projects place the original three brackets on their retangented diagonal rear face (about X=133–134 degrees, depending on depth). The shallow brackets use Y=-90 degrees with a broad side down and request normal Auto support on those objects. In both checked H2D PETG profiles, shallow-bracket support touched the floor and wall X mating regions. Those regions are exposed in the side-down pose, but the support must be removed completely before checking fit.

## Normal and angled cargo stops

`vertical-stop` is a filled triangular cargo wedge, not a tile holder or a request for 100% slicer infill. The catalogue has 1x1, 1x2, 2x1 and 2x2 bases at 60 mm and 120 mm shoulder heights.

![Eight normal stops covering four base sizes and two heights.](docs/images/vertical-stops.png)

```sh
uv run cargo-grid part --family vertical-stop --width-cells 2 --depth-cells 1 --stop-height-mm 120 --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --bambu --material "Model PETG" PETG "#637b70" --nozzle-diameter-mm 0.4 --layer-height-mm 0.2 --output outputs/vertical-stop
```

Every free outer edge is R2; the X plugs and roots stay unchanged. Bambu rotates each normal stop onto its broad rear face and enables normal Auto support on that object. The 1x1/H120 and 2x1/H120 variants produced support in the mounting region during the checked H2D slices, so remove it before testing fit.

The two `lock-45` angled stops are also filled wedges. Their free body edges are R2, their X geometry is unchanged and Bambu places them X=-135 degrees with the rear face down.

## Floor ramps

`ramp` makes a floor-to-mat transition whose rise follows tile thickness. Its run stays fixed at 50 mm; width grows in the selected unit size, and each unit repeats one matching original roofed female tile-edge pocket.

![Five ramps from one to five cells wide.](docs/images/ramps.png)

```sh
uv run cargo-grid part --family ramp --width-cells 3 --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --bambu --material "Model PETG" PETG "#637b70" --nozzle-diameter-mm 0.4 --layer-height-mm 0.2 --output outputs/ramp
```

The ramp receives a tile's north male edge and extends away in positive Y. Custom unit size/thickness work with matching original roofed interfaces; full-height ramp joints remain unsupported. Normal Auto support is limited to the exposed female-pocket roofs and must be removed before assembly.

## Support the underside joint bridges

The receiving side of an original tile joint has a small bridge or ceiling over an open pocket. Cargo-Grid calls that ceiling the **roof**. If you print it without enough bridging performance, it can sag into the joint.

For a two-nozzle PETG tile with a PLA contact interface, Cargo-Grid can add removable support under the west/south roofs:

```sh
uv run cargo-grid part --build-width-mm 350 --build-depth-mm 320 --build-height-mm 325 --build-margin-mm 37 --width-cells 2 --depth-cells 1 --copy-count 2 --bambu --material "Model PETG" PETG "#778877" --material "Interface PLA" PLA "#dddddd" --nozzle-diameter-mm 0.8 --layer-height-mm 0.32 --roof-support --output outputs/roof-job
```

Open `outputs/roof-job/job.3mf` as a project and choose your actual printer, bed, process and filament profiles. Cargo-Grid sets PETG for the model/support base and PLA for the dense top interface, with:

| Setting | Value |
| --- | --- |
| Top contact distance | 0 mm |
| Independent support layer height | off |
| Top interface spacing | 0 mm |
| Top interface layers | 2 |
| Build plate only | off |
| Support/object XY distance | 0.40 mm |

This zero-gap contact is only for the PETG/PLA pairing. Do not use it with the same material on both sides or an untested pair that may fuse.

Before printing:

1. Check the printer, bed and PETG/PLA assignments.
2. Slice and inspect the roof from below. The PLA interface must meet the bottom of the first PETG roof layer.
3. Check that the protected X openings remain clear.
4. On a full-hole 2x1 tile, support intentionally occupies the three round edge cutouts at (0,30), (30,0) and (90,0) during printing. Remove it through the open underside/female edge afterward.
5. Recheck support, brim, tower and warnings whenever the profile or material changes.

## CLI reference

```sh
uv run cargo-grid --help
uv run cargo-grid part --help
uv run cargo-grid layout --help
uv run cargo-grid catalogue --help
```

`part` makes one design, `layout` fills a requested rectangle and `catalogue` enumerates everything that fits. Normal generation does not need a downloaded reference model. `compare-reference` is an optional maintainer check described in the [release checklist](docs/release-checklist.md#optional-native-and-reference-checks).

Common options:

- `--build-width-mm`, `--build-depth-mm`, `--build-height-mm`: available X/Y/Z print space;
- `--unit-size-mm`: cell size and matching nominal local-plane interface scale, default 60 mm;
- `--tile-thickness-mm`: independent body thickness and connector insertion depth, default 13 mm;
- `--width-cells`, `--depth-cells`: one tile or two-axis accessory;
- `--panel-height-cells`: bracket wall rows, separate from floor depth;
- `--length-cells`: edge strips and support rails;
- `--copy-count`: repeated copies of one design;
- `--layout-width-mm`, `--layout-depth-mm`: finished rectangular layout;
- `--packing-gap-mm`: catalogue separation.

This alpha removed earlier ambiguous names. The main replacements are:

| Earlier option | Current option |
| --- | --- |
| `--cells X Y` | `--width-cells X --depth-cells Y` |
| `--footprint W D` | `--layout-width-mm W --layout-depth-mm D` |
| `--quantity N` | `--copy-count N` |
| `--margin` | `--build-margin-mm` |
| `--part-gap` | `--packing-gap-mm` |
| `--pitch`, `--grid-pitch-mm` | `--unit-size-mm` |
| `--height`, `--tile-height-mm` | `--tile-thickness-mm` |
| `--fit-offset` | `--fit-offset-mm` |
| `--nozzle`, `--layer-height`, `--hole-diameter` | `--nozzle-diameter-mm`, `--layer-height-mm`, `--hole-diameter-mm` |
| `--accessory-height`, `--length`, `--variant` | `--stop-height-mm`, `--connector-length-mm`, `--variant-number` |

See `--help` for build reservations/exclusions, stacking and advanced roof-support settings.

## Compatibility notes

Original roofed joints are the default. At the standard 60 mm unit and 13 mm thickness, the male ledge reaches Z=10 and the female roof is Z=10.2. Unit size scales cells, X outlines and tile-edge joint profiles in their local plane. Tile thickness independently controls body thickness, plug depth and roof/ledge heights. Fit offset, the 0.2 mm plug gap and comfort radii remain absolute millimeters.

`--joint-style full-height` is an optional open-through tile-edge-joint experiment. It is unrelated to 60/120 mm cargo-stop height or printer build height. At standard 60/13 dimensions, its open female pockets leave a very thin upper web, and its male tabs do not fit original roofed female pockets. Read the [geometry contract](docs/geometry.md) before changing interfaces or validation tolerances.

The full 10 mm hole pattern is on by default. Use `--no-holes` to opt out. The manifest records holes rejected by an interface or edge keep-out.

## Stacking identical tiles

Stacking adds sacrificial support-base and release-interface volumes between copies of the same tile:

```sh
uv run cargo-grid part --build-width-mm 150 --build-depth-mm 150 --build-height-mm 70 --width-cells 1 --depth-cells 1 --copy-count 4 --bambu --material "Model PETG" PETG "#778877" --material "Release PLA" PLA "#dddddd" --nozzle-diameter-mm 0.4 --layer-height-mm 0.2 --stack-count 2 --stack-gap-mm 1 --stack-interface-thickness-mm 0.2 --stack-material-slots 1 1 2 --output outputs/stack-job
```

`--stack-count auto` uses the available height. Roof support and stacking cannot be combined, and mixed catalogue stacking is not supported.

## Python API and development

```python
from pathlib import Path
from cargo_grid import BuildVolume, Tile
from cargo_grid.export import export_job
from cargo_grid.jobs import Job, tile_design

design = tile_design(Tile(nx=2, ny=1))
export_job(Job([design], BuildVolume(150, 150, 50), "part"), Path("outputs/python-job"))
```

Accessory example:

```python
from cargo_grid.accessories import Accessory
from cargo_grid.catalogue import accessory_design

bracket = accessory_design(Accessory("vertical-tile-bracket", nx=1, ny=1, panel_height_cells=2))
```

Development checks:

```sh
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q -n 12 --dist loadfile -m "not native and not reference"
uv build
uv run python tools/check_distributions.py dist
```

Twelve process workers were fastest for the full portable suite on the measured maintainer workstation; use fewer on smaller machines. CI uses two on its runner. Keep native/reference tests serial. They use explicitly supplied `CARGO_GRID_BAMBU` and `CARGO_GRID_REFERENCE` and skip when those resources are unavailable. Keep `uv.lock` local and ignored. See [AGENTS.md](AGENTS.md), the [release checklist](docs/release-checklist.md) and [gallery reproduction instructions](docs/attachments.md#reproduce-the-images) for maintainer details.

## License and reference boundary

[The MIT license](LICENSE) covers this source code. Functional measurements of Tora.'s MakerWorld trunk-organizer mat informed the interface work; that model has separate terms. This repository does not include its meshes, images, profiles or private files.

Python parameters are the editable design source. STEP, STL, 3MF and gallery images are generated from it. Cargo-Grid does not connect to a printer or start prints.
