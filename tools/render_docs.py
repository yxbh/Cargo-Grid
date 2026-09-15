"""Render the documented finite catalogue using an external approved CAD workbench."""

import argparse
import hashlib
import json
import math
import os
import struct
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from cargo_grid import BuildVolume, Tile, make_tile
from cargo_grid.accessories import SUPPORT_END_NAMES, Accessory, make_accessory
from cargo_grid.catalogue import accessory_variants

ROOT = Path(__file__).resolve().parents[1]
BUILD = BuildVolume(350, 320, 325)
WORKBENCH_REVISION = "120024625ad5c76a5d8bc768556e04fc7eae4023"
CAMERA = "45:32"
BACKGROUND = "#f2f1ec"
IMAGE_NAMES = ("hero.png", "straight-members.png", "corners-connectors.png", "x-attachments.png")
SHEETS = (
    ("straight-members.png", "Straight members", ("edge-x", "edge-y", "support"), 5),
    (
        "corners-connectors.png",
        "Corners & rail connectors",
        ("corner-in", "corner-out", "support-end", "support-bit"),
        6,
    ),
    ("x-attachments.png", "X-plug attachments", ("plate", "lock-90", "lock-45"), 4),
)


@dataclass(frozen=True)
class Item:
    key: str
    title: str
    detail: str
    spec: Accessory | None = None


def inventory() -> list[Item]:
    items = []
    for spec in accessory_variants(BUILD):
        if spec.family in ("edge-x", "edge-y", "support"):
            suffix, detail = str(spec.nx), f"{spec.nx} cell" + ("s" if spec.nx != 1 else "")
        elif spec.family == "support-bit":
            suffix, detail = f"{spec.length:g}mm", f"{spec.length:g} mm length"
        elif spec.family in ("corner-in", "corner-out", "support-end"):
            suffix, detail = f"v{spec.variant}", f"variant {spec.variant}"
            if spec.family == "support-end":
                detail += f" / {SUPPORT_END_NAMES[spec.variant - 1]}"
        else:
            suffix, detail = f"{spec.nx}x{spec.ny}", f"{spec.nx} x {spec.ny}"
            if spec.family.startswith("lock-"):
                detail += f" / H {spec.height:g} mm"
        items.append(Item(f"{spec.family}-{suffix}", spec.family, detail, spec))
    return items


def hero_items() -> list[Item]:
    return [
        Item("tile-default", "Original joining geometry", "2 x 1 / no optional holes"),
        Item("tile-full", "An optional open pattern", "2 x 1 / 13 extra 10 mm holes"),
    ]


def documentation_shape(key: str):
    from build123d import Color

    if key in ("tile-default", "tile-full"):
        shape = make_tile(
            Tile(
                2,
                1,
                hole_diameter=10 if key == "tile-full" else None,
                hole_scope="full" if key == "tile-full" else "interior",
            )
        )
        shape.label = key
        color = "#637b70" if key == "tile-full" else "#4b5752"
    else:
        item = next(item for item in inventory() if item.key == key)
        shape = make_accessory(item.spec)
        color = "#637b70" if item.spec.family in ("plate", "lock-90", "lock-45") else "#626b68"
    if not shape.is_valid or len(shape.solids()) != 1 or shape.volume <= 0:
        raise ValueError(f"Invalid documentation geometry: {key}")
    shape.color = Color(color)
    return shape


def projected_spans(size) -> tuple[float, float]:
    azimuth, elevation = map(math.radians, (45, 32))
    x, y, z = size
    return (
        abs(math.sin(azimuth)) * x + abs(math.cos(azimuth)) * y,
        math.sin(elevation) * (math.cos(azimuth) * x + math.sin(azimuth) * y)
        + math.cos(elevation) * z,
    )


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"Not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def verify_assets() -> dict:
    paths = [ROOT / "docs/images" / name for name in IMAGE_NAMES]
    report = {}
    for path in paths:
        width, height = png_size(path)
        size = path.stat().st_size
        if width != 1800 or height < 500 or size > 1_500_000:
            raise ValueError(f"Unexpected dimensions or size: {path.name}")
        report[path.name] = {
            "dimensions": [width, height],
            "bytes": size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    if sum(p.stat().st_size for p in paths) > 4_000_000:
        raise ValueError("Documentation composites exceed the 4 MB budget")
    table = (ROOT / "docs/attachments.md").read_text()
    for item in inventory():
        if f"`{item.key}`" not in table:
            raise ValueError(f"Inventory omits {item.key}")
    return report


def run(command, log: Path, environment: dict) -> None:
    with log.open("w") as output:
        result = subprocess.run(
            command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT
        )
    if result.returncode:
        raise RuntimeError(f"Documentation tool failed; inspect {log.relative_to(ROOT)}")


def render_items(workbench: Path, work: Path, only: set[str] | None) -> dict:
    revision = subprocess.check_output(
        ["git", "-C", str(workbench), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != WORKBENCH_REVISION:
        raise ValueError(f"Use the documented workbench revision {WORKBENCH_REVISION}")
    subprocess.run(
        ["git", "diff", "--exit-code", "HEAD", "--", "src/cargo_grid"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    source_tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD:src/cargo_grid"], cwd=ROOT, text=True
    ).strip()
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    recipe_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    python = workbench / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    tools = workbench / ".agents/skills/cad/scripts"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src")))
    for subdir in ("source", "steps", "renders", "facts", "logs"):
        (work / subdir).mkdir(parents=True, exist_ok=True)
    items = hero_items() + inventory()
    if only and not only <= {item.key for item in items}:
        raise ValueError("Unknown --only item")
    for item in items:
        if only and item.key not in only:
            continue
        key = item.key
        source, step, image, facts = (
            work / "source" / f"{key}.py",
            work / "steps" / f"{key}.step",
            work / "renders" / f"{key}.png",
            work / "facts" / f"{key}.json",
        )
        cache = {"source_tree": source_tree, "workbench": revision, "recipe": recipe_hash}
        if (
            image.exists()
            and facts.exists()
            and json.loads(facts.read_text()).get("cache") == cache
        ):
            continue
        source.write_text(
            "import json\nfrom pathlib import Path\nfrom tools.render_docs import documentation_shape\n\n"
            "def gen_step():\n"
            f"    shape = documentation_shape({key!r})\n"
            f"    facts = {{'key': {key!r}, 'public_name': shape.label, 'size_mm': tuple(shape.bounding_box().size), 'volume_mm3': shape.volume, 'valid': shape.is_valid, 'solids': len(shape.solids()), 'cache': {cache!r}}}\n"
            f"    Path({facts.relative_to(ROOT).as_posix()!r}).write_text(json.dumps(facts, indent=2) + '\\n')\n"
            "    return shape\n"
        )
        run(
            [
                str(python),
                str(tools / "step"),
                source.relative_to(ROOT).as_posix(),
                "-o",
                step.relative_to(ROOT).as_posix(),
            ],
            work / "logs" / f"{key}-step.log",
            environment,
        )
        run(
            [
                str(python),
                str(tools / "inspect"),
                "refs",
                step.relative_to(ROOT).as_posix(),
                "--facts",
                "--planes",
                "--positioning",
            ],
            work / "logs" / f"{key}-inspect.json",
            environment,
        )
        inspection = json.loads((work / "logs" / f"{key}-inspect.json").read_text())
        if not inspection["ok"] or inspection["errors"]:
            raise ValueError(f"STEP inspection failed: {key}")
        width, height = (1000, 650) if item.spec is None else (600, 360)
        run(
            [
                str(python),
                str(tools / "render"),
                "view",
                step.relative_to(ROOT).as_posix(),
                "--output",
                image.relative_to(ROOT).as_posix(),
                "--camera",
                CAMERA,
                "--width",
                str(width),
                "--height",
                str(height),
                "--background",
                BACKGROUND,
                "--preset",
                "solid",
                "--color-by",
                "step",
                "--edges",
                "thin",
                "--no-axes",
                "--quality",
                "high",
                "--timeout-seconds",
                "120",
            ],
            work / "logs" / f"{key}-render.log",
            environment,
        )
        print(f"Rendered {key}", flush=True)
    if (
        subprocess.check_output(
            ["git", "-C", str(workbench), "rev-parse", "HEAD"], text=True
        ).strip()
        != revision
    ):
        raise ValueError(
            "Workbench revision changed during rendering; do not publish mixed-revision assets"
        )
    return {
        "generator_commit": source_commit,
        "generator_tree": source_tree,
        "workbench_commit": revision,
        "recipe_sha256": recipe_hash,
    }


def composite(
    work: Path, items: list[Item], filename: str, title: str, columns: int, hero=False
) -> dict:
    from PIL import Image, ImageDraw, ImageFont

    width, margin, header = 1800, 40, 0 if hero else 150
    cell_width = (width - 2 * margin) // columns
    image_height, row_height = (530, 640) if hero else (260, 350)
    rows = math.ceil(len(items) / columns)
    height = header + rows * row_height + 50
    background = (
        Image.open(work / "renders" / f"{items[0].key}.png").convert("RGB").getpixel((0, 0))
    )
    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)
    heading = ImageFont.load_default(size=56)
    label = ImageFont.load_default(size=36 if columns < 6 else 32)
    detail = ImageFont.load_default(size=27 if columns < 6 else 25)
    ink, muted = "#253b33", "#52685e"
    if not hero:
        draw.text((margin, 26), title, font=heading, fill=ink)
        draw.text(
            (margin, 98),
            f"{len(items)} variants / 350 x 320 x 325 mm catalogue envelope / original joints",
            font=detail,
            fill=muted,
        )
    facts = {
        item.key: json.loads((work / "facts" / f"{item.key}.json").read_text()) for item in items
    }
    spans = [projected_spans(facts[item.key]["size_mm"]) for item in items]
    scale = 0.94 * min(
        (cell_width - 24) / max(s[0] for s in spans), (image_height - 20) / max(s[1] for s in spans)
    )
    for index, item in enumerate(items):
        x = margin + (index % columns) * cell_width
        y = header + (index // columns) * row_height
        with Image.open(work / "renders" / f"{item.key}.png") as raw:
            raw = raw.convert("RGB")
            sx, sy = projected_spans(facts[item.key]["size_mm"])
            units_per_pixel = 1.03 * max(sy, sx * raw.height / raw.width) / raw.height
            factor = scale * units_per_pixel
            rendered = raw.resize(
                (round(raw.width * factor), round(raw.height * factor)), Image.Resampling.LANCZOS
            )
        canvas.paste(
            rendered,
            (x + (cell_width - rendered.width) // 2, y + (image_height - rendered.height) // 2),
        )
        draw.text((x + 12, y + image_height + 6), item.title, font=label, fill=ink)
        draw.text((x + 12, y + image_height + 50), item.detail, font=detail, fill=muted)
    output = ROOT / "docs/images" / filename
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, optimize=True)
    return {
        "file": output.relative_to(ROOT).as_posix(),
        "items": [item.key for item in items],
        "pixels_per_mm_at_source_resolution": scale,
        "dimensions": [width, height],
    }


def compose_all(work: Path, provenance: dict) -> None:
    items = inventory()
    sheets = [composite(work, hero_items(), "hero.png", "", 2, hero=True)]
    for filename, title, families, columns in SHEETS:
        selected = [item for family in families for item in items if item.spec.family == family]
        sheets.append(composite(work, selected, filename, title, columns))
    gallery = {key: sheet["file"] for sheet in sheets for key in sheet["items"]}
    lines = [
        "# Complete attachment inventory",
        "",
        "This gallery covers every attachment variant returned by `accessory_variants(BuildVolume(350, 320, 325))` with original joints and default accessory parameters. It contains 44 variants, all rendered from the generator's actual STEP geometry. Other build envelopes and explicit parametric lengths/heights can produce additional variants; this is not an exhaustive list of an unbounded parameter space.",
        "",
        "All views use the same 45-degree azimuth / 32-degree elevation. Each sheet uses a common physical scale; scales differ between sheets for legibility. Colors are illustrative, not material/profile assignments. Open an image at full size for detail.",
        "",
        "| Inventory key | Public API shape label | Geometry parameters | Sheet |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        facts = json.loads((work / "facts" / f"{item.key}.json").read_text())
        dims = " x ".join(f"{v:.1f}" for v in facts["size_mm"])
        lines.append(
            f"| `{item.key}` | `{facts['public_name']}` | {item.detail}; bounds {dims} mm | [View]({Path(gallery[item.key]).relative_to('docs').as_posix()}) |"
        )
    lines += [
        "",
        "## Reproduce the images",
        "",
        "Use an external CAD-Pilot checkout at the documented workbench revision with its existing render dependencies installed. No documentation dependency is added to Cargo-Grid's runtime. From this repository root, run:",
        "",
        "```sh",
        "PYTHONPATH=src <workbench-python> tools/render_docs.py --workbench <workbench-checkout>",
        "```",
        "",
        "Use the workbench's Python interpreter with Pillow already available; paths are supplied locally, not committed. In PowerShell, set `$env:PYTHONPATH='src'` before invoking that interpreter. The script invokes the workbench STEP, inspection and render launchers from this project, then composes only the four intentional PNG assets. Intermediate generators, STEP files, raw renders and detailed evidence stay under ignored outputs. Inventory, camera and layout are deterministic; exact raster pixels can depend on the graphics/Pillow environment.",
        "",
        f"Generator source revision: `{provenance['generator_commit']}`. Generator tree: `{provenance['generator_tree']}`. Workbench revision: `{provenance['workbench_commit']}`.",
        "",
        "A successful render is not evidence of printability, physical fit, support release or third-party design rights.",
        "",
    ]
    (ROOT / "docs/attachments.md").write_text("\n".join(lines))
    report = {
        **provenance,
        "composition_recipe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "build_mm": [350, 320, 325],
        "attachment_count": len(items),
        "variants": [
            {
                "key": item.key,
                "parameters": asdict(item.spec),
                **json.loads((work / "facts" / f"{item.key}.json").read_text()),
            }
            for item in items
        ],
        "sheets": sheets,
        "assets": verify_assets(),
    }
    (work / "render-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["assets"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbench", type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path("outputs/docs-render/gallery"))
    parser.add_argument(
        "--only",
        nargs="+",
        help="render a bounded subset without composing a purported complete gallery",
    )
    parser.add_argument("--compose-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(verify_assets(), indent=2))
        return
    if args.workbench is None:
        parser.error("--workbench is required for rendering")
    work = (ROOT / args.work_dir).resolve()
    work.relative_to(ROOT)
    if args.compose_only:
        provenance = json.loads((work / "provenance.json").read_text())
    else:
        provenance = render_items(
            args.workbench.resolve(), work, set(args.only) if args.only else None
        )
        (work / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    if not args.only:
        compose_all(work, provenance)


if __name__ == "__main__":
    main()
