"""Render the documented finite catalogue using an external approved CAD workbench."""

import argparse
import hashlib
import json
import math
import os
import re
import struct
import subprocess
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path

from cargo_grid import BuildVolume, Interface, Tile, make_tile
from cargo_grid.accessories import (
    SUPPORT_END_NAMES,
    VERTICAL_BRACKET_CONFIGS,
    Accessory,
    make_accessory,
)
from cargo_grid.catalogue import BRACKET_DISPLAY_NAMES, accessory_variants

ROOT = Path(__file__).resolve().parents[1]
BUILD = BuildVolume(350, 320, 325)
WORKBENCH_REVISION = "c3f63ef8d8604d3ec7eeba40a229047887c03d86"
GEOMETRY_REVISION = "839b1b83ef628a40fe69842d55b43246215fbd6b"
GEOMETRY_FILES = (
    "parameters.py",
    "interfaces.py",
    "tiles.py",
    "accessories.py",
    "catalogue.py",
    "jobs.py",
    "layout.py",
    "packing.py",
)
CAMERA = "45:32"
BACKGROUND = "#f2f1ec"
IMAGE_NAMES = (
    "hero.png",
    "x-attachments.png",
    "vertical-tile-brackets.png",
    "vertical-stops.png",
    "ramps.png",
    "interface-sizes.png",
)
SHEETS = (
    (
        "x-attachments.png",
        "X-plug attachments",
        ("plate", "vertical-tile-bracket", "vertical-stop", "lock-45"),
        4,
    ),
)
FAMILIES = {
    "ramp": (
        "Floor ramps",
        "A floor-to-mat transition with a fixed 50 mm run. Width and its original roofed female pocket follow unit size; rise follows tile thickness. Normal Auto support is scoped to exposed pocket roofs.",
    ),
    "plate": (
        "Attachment plates",
        "A flat R2 body with exact X plugs underneath. Bambu projects place its broad body face down so the plugs grow upward.",
    ),
    "vertical-tile-bracket": (
        "Vertical tile brackets",
        "A filled wedge carrying a separate ordinary tile vertically. All five use R3 at the exposed front-to-slope transition; two shallow variants keep one floor row under a two-row wall.",
    ),
    "vertical-stop": (
        "Normal full-solid stops",
        "A full-width filled cargo wedge with no wall holes or open ribs. Every free outer edge is R2 while X plugs remain exact. Bambu projects place its broad rear face down and scope normal Auto support to this object.",
    ),
    "lock-45": (
        "Angled stops",
        "A full-width filled angled cargo wedge with a 6 mm horizontal cap and R2 on every free body edge. Exact X plugs and roots remain protected. Use the recommended back-face-down print pose.",
    ),
    "edge-x": (
        "Male edge strips",
        "An R3 finishing strip with male tile-facing joins; length follows the cell count.",
    ),
    "edge-y": (
        "Female edge strips",
        "An R3 finishing strip with female tile-facing joins; length follows the cell count.",
    ),
    "corner-in": (
        "Inner corners",
        "An R3 corner finishing piece in one of four supported joining arrangements.",
    ),
    "corner-out": (
        "Outer corners",
        "An R3 outer-edge finishing piece in one of six supported arrangements.",
    ),
    "support": (
        "Support rails",
        "An R3 physical bearing rail with rounded windows and separate end-to-end joins.",
    ),
    "support-end": (
        "Rail ends",
        "A rounded ramped rail end; X, Xs, Y and Ys select the supported arrangements.",
    ),
    "support-bit": (
        "Rail connectors",
        "A rounded rail connector with a projecting join; the label gives its specified length.",
    ),
}
THUMBNAIL_SIZE = (480, 300)


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
        elif spec.family == "ramp":
            suffix = str(spec.nx)
            detail = f"{spec.nx} cell width / 50 mm run"
        elif spec.family == "support-bit":
            suffix, detail = f"{spec.length:g}mm", f"{spec.length:g} mm length"
        elif spec.family in ("corner-in", "corner-out", "support-end"):
            suffix, detail = f"v{spec.variant}", f"variant {spec.variant}"
            if spec.family == "support-end":
                detail += f" / {SUPPORT_END_NAMES[spec.variant - 1]}"
        elif spec.family == "vertical-stop":
            suffix = f"{spec.nx}x{spec.ny}-h{spec.height:g}"
            detail = f"{spec.nx} x {spec.ny} / H {spec.height:g} mm"
        elif spec.family == "vertical-tile-bracket":
            panel_rows = spec.panel_height_cells or spec.ny
            if spec.panel_height_cells is None:
                suffix = f"{spec.nx}x{spec.ny}"
            else:
                suffix = f"base{spec.nx}x{spec.ny}-wall{spec.nx}x{panel_rows}"
            detail = f"floor base {spec.nx} x {spec.ny} / wall {spec.nx} x {panel_rows}"
        else:
            suffix, detail = f"{spec.nx}x{spec.ny}", f"{spec.nx} x {spec.ny}"
            if spec.family.startswith("lock-"):
                detail += f" / H {spec.height:g} mm"
        items.append(Item(f"{spec.family}-{suffix}", spec.family, detail, spec))
    return items


def hero_items() -> list[Item]:
    return [
        Item("tile-default", "Default full-hole 4x4 tile", "65 additional 10 mm holes"),
        Item("tile-no-holes", "No-hole 4x4 tile", "Explicit solid-web opt-out"),
    ]


def interface_scale_items() -> list[Item]:
    return [
        Item(
            "interface-standard",
            "Standard interface",
            "60 mm unit / 13 mm thickness",
        ),
        Item(
            "interface-compact",
            "Compact matching interface",
            "30 mm unit / 13 mm thickness",
        ),
    ]


def bracket_assembly_items() -> list[Item]:
    return [
        Item(
            f"bracket-context-base{x}x{base_y}-wall{x}x{panel_z}",
            BRACKET_DISPLAY_NAMES[(x, base_y, panel_z)].replace(" — ", " - "),
            (
                f"Floor {60 * x} x {60 * base_y} mm / wall {60 * x} x {60 * panel_z} mm"
                f" / {'top' if panel_z != base_y else 'underside'} face outward"
            ),
        )
        for x, base_y, panel_z in VERTICAL_BRACKET_CONFIGS
    ]


def documentation_shape(key: str):
    from build123d import Axis, Color, Compound, Location

    if key.startswith("interface-"):
        interface = Interface(60 if key == "interface-standard" else 30, 13)
        tile = make_tile(Tile(1, 1, interface, hole_diameter=None))
        plate = make_accessory(Accessory("plate", interface=interface)).moved(
            Location((0, 0, interface.height + interface.plug_depth + 4))
        )
        tile.color, plate.color = Color("#b9c6c0"), Color("#637b70")
        shape = Compound(children=[tile, plate], label=key)
        if not shape.is_valid or len(shape.solids()) != 2:
            raise ValueError(f"Invalid exploded interface comparison: {key}")
        return shape

    if key.startswith("bracket-context-"):
        nx, base_y, panel_z = next(
            config
            for config in VERTICAL_BRACKET_CONFIGS
            if key == f"bracket-context-base{config[0]}x{config[1]}-wall{config[0]}x{config[2]}"
        )
        bracket = make_accessory(
            Accessory(
                "vertical-tile-bracket",
                nx=nx,
                ny=base_y,
                panel_height_cells=panel_z if panel_z != base_y else None,
            )
        ).moved(Location((0, 0, 13)))
        floor = make_tile(Tile(nx, base_y))
        wall = make_tile(Tile(nx, panel_z, hole_diameter=10, hole_scope="full"))
        if panel_z != base_y:
            wall = (
                wall.rotate(Axis.Z, 180)
                .rotate(Axis.X, -90)
                .moved(Location((nx * 60, base_y * 60 - 13, 19.1)))
            )
        else:
            wall = wall.rotate(Axis.X, 90).moved(Location((0, base_y * 60, 19.1)))
        floor.color, bracket.color, wall.color = (
            Color("#b9c6c0"),
            Color("#637b70"),
            Color("#c2cecb"),
        )
        shape = Compound(children=[floor, bracket, wall], label=key)
        if not shape.is_valid or len(shape.solids()) != 3:
            raise ValueError(f"Invalid separate-tile illustration: {key}")
        return shape

    if key in ("tile-default", "tile-no-holes"):
        shape = make_tile(
            Tile(
                4,
                4,
                hole_diameter=None if key == "tile-no-holes" else 10,
                hole_scope="full",
            )
        )
        shape.label = key
        color = "#637b70" if key == "tile-default" else "#4b5752"
    else:
        item = next(item for item in inventory() if item.key == key)
        shape = make_accessory(item.spec)
        color = (
            "#637b70"
            if item.spec.family
            in ("ramp", "plate", "vertical-tile-bracket", "vertical-stop", "lock-45")
            else "#626b68"
        )
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


def thumbnail_tag(entry: dict) -> str:
    return f'<a href="{entry["file"]}"><img src="{entry["file"]}" alt="{escape(entry["alt"], quote=True)}" width="180" height="113"></a>'


def revision_tag(value: str) -> str:
    return (
        "<code>"
        + "<wbr>".join(escape(value[i : i + 8]) for i in range(0, len(value), 8))
        + "</code>"
    )


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
    manifest = json.loads((ROOT / "docs/images/attachments/manifest.json").read_text())
    overviews = manifest["overview_images"]
    if len(overviews) != len(IMAGE_NAMES) or {entry["file"] for entry in overviews} != {
        f"images/{name}" for name in IMAGE_NAMES
    }:
        raise ValueError("Overview manifest does not match the documented image set")
    for entry in overviews:
        name = Path(entry["file"]).name
        if entry["sha256"] != report[name]["sha256"]:
            raise ValueError(f"Overview hash mismatch: {name}")
    items = inventory()
    entries = manifest["items"]
    if len(entries) != len(items) or {entry["key"] for entry in entries} != {
        item.key for item in items
    }:
        raise ValueError("Thumbnail manifest does not match the complete API inventory")
    actual_files = {p.name for p in (ROOT / "docs/images/attachments").iterdir()}
    if actual_files != {"manifest.json", *(f"{item.key}.png" for item in items)}:
        raise ValueError("Unexpected or missing attachment thumbnail files")
    for item in items:
        entry = next(entry for entry in entries if entry["key"] == item.key)
        path = ROOT / "docs" / entry["file"]
        if entry["file"] != f"images/attachments/{item.key}.png" or entry[
            "parameters"
        ] != json.loads(json.dumps(asdict(item.spec))):
            raise ValueError(f"Thumbnail identity mismatch: {item.key}")
        if png_size(path) != THUMBNAIL_SIZE or path.stat().st_size > 70_000:
            raise ValueError(f"Thumbnail dimensions/size out of budget: {item.key}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Thumbnail hash mismatch: {item.key}")
        image = thumbnail_tag(entry)
        rows = [row for row in table.splitlines() if image in row]
        if (
            len(rows) != 1
            or f"<code>{entry['public_name']}</code>" not in rows[0].replace("<wbr>", "")
            or f"<code>{item.key}</code>" not in rows[0]
        ):
            raise ValueError(f"Thumbnail/name/alt mapping is not one-to-one: {item.key}")
        report[f"attachments/{item.key}.png"] = {
            "dimensions": list(THUMBNAIL_SIZE),
            "bytes": path.stat().st_size,
            "sha256": entry["sha256"],
        }
    if len(re.findall(r'<img src="images/attachments/[^"]+"', table)) != len(items):
        raise ValueError("Expected exactly one visible thumbnail per inventory row")
    if len({entry["sha256"] for entry in entries}) != len(items):
        raise ValueError("Attachment thumbnails must be distinct, not repeated generic pictures")
    if sum(asset["bytes"] for asset in report.values()) > 2_000_000:
        raise ValueError("Documentation images exceed the 2 MB budget")
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
    verify_geometry_source()
    source_tree = subprocess.check_output(
        ["git", "rev-parse", f"{GEOMETRY_REVISION}:src/cargo_grid"], cwd=ROOT, text=True
    ).strip()
    source_commit = GEOMETRY_REVISION
    recipe_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    python = workbench / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    tools = workbench / ".agents/skills/cad/scripts"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(ROOT), str(ROOT / "src")))
    for subdir in ("source", "steps", "renders", "facts", "logs"):
        (work / subdir).mkdir(parents=True, exist_ok=True)
    items = hero_items() + interface_scale_items() + inventory() + bracket_assembly_items()
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


def verify_geometry_source() -> None:
    for name in GEOMETRY_FILES:
        relative = f"src/cargo_grid/{name}"
        committed = subprocess.check_output(
            ["git", "show", f"{GEOMETRY_REVISION}:{relative}"], cwd=ROOT
        )
        if committed != (ROOT / relative).read_bytes():
            raise ValueError(f"Documentation geometry differs from {GEOMETRY_REVISION}: {relative}")


def thumbnail_entries(work: Path, provenance: dict) -> list[dict]:
    from PIL import Image

    if (
        provenance["generator_commit"] != GEOMETRY_REVISION
        or provenance["workbench_commit"] != WORKBENCH_REVISION
    ):
        raise ValueError("Cached renders have unexpected geometry/workbench provenance")
    target = ROOT / "docs/images/attachments"
    target.mkdir(parents=True, exist_ok=True)
    entries = []
    for family in FAMILIES:
        items = [item for item in inventory() if item.spec.family == family]
        facts = {
            item.key: json.loads((work / "facts" / f"{item.key}.json").read_text())
            for item in items
        }
        spans = [projected_spans(facts[item.key]["size_mm"]) for item in items]
        scale = 0.88 * min(
            THUMBNAIL_SIZE[0] / max(s[0] for s in spans),
            THUMBNAIL_SIZE[1] / max(s[1] for s in spans),
        )
        for item in items:
            fact = facts[item.key]
            if (
                not fact["valid"]
                or fact["solids"] != 1
                or fact["cache"]["source_tree"] != provenance["generator_tree"]
            ):
                raise ValueError(f"Unverified render geometry: {item.key}")
            source = work / "renders" / f"{item.key}.png"
            inspection = json.loads((work / "logs" / f"{item.key}-inspect.json").read_text())
            step = work / "steps" / f"{item.key}.step"
            step_sha = hashlib.sha256(step.read_bytes()).hexdigest()
            if (
                not inspection["ok"]
                or inspection["errors"]
                or inspection["tokens"][0]["stepHash"] != step_sha
            ):
                raise ValueError(f"Cached STEP inspection no longer matches: {item.key}")
            with Image.open(source) as raw:
                raw = raw.convert("RGB")
                sx, sy = projected_spans(fact["size_mm"])
                units_per_pixel = 1.03 * max(sy, sx * raw.height / raw.width) / raw.height
                factor = scale * units_per_pixel
                resized = raw.resize(
                    (round(raw.width * factor), round(raw.height * factor)),
                    Image.Resampling.LANCZOS,
                )
                image = Image.new("RGB", THUMBNAIL_SIZE, raw.getpixel((0, 0)))
                image.paste(
                    resized,
                    ((image.width - resized.width) // 2, (image.height - resized.height) // 2),
                )
            path = target / f"{item.key}.png"
            image.save(path, optimize=True)
            entries.append(
                {
                    "key": item.key,
                    "family": family,
                    "public_name": fact["public_name"],
                    "parameters": asdict(item.spec),
                    "size_mm": fact["size_mm"],
                    "file": path.relative_to(ROOT / "docs").as_posix(),
                    "alt": f"{item.title}, {item.detail}, original joints: isometric STEP-derived render",
                    "description": FAMILIES[family][1],
                    "dimensions": list(THUMBNAIL_SIZE),
                    "pixels_per_mm": scale,
                    "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "source_render_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "source_step_sha256": step_sha,
                }
            )
    manifest = {
        "geometry_commit": GEOMETRY_REVISION,
        "workbench_commit": WORKBENCH_REVISION,
        "catalogue_build_mm": {"width_x": 350, "depth_y": 320, "height_z": 325},
        "camera": CAMERA,
        "scale": "Common physical scale within each family; families differ.",
        "source_render_recipe_sha256": provenance["recipe_sha256"],
        "overview_images": [
            {
                "file": f"images/{name}",
                "dimensions": list(png_size(ROOT / "docs/images" / name)),
                "bytes": (ROOT / "docs/images" / name).stat().st_size,
                "sha256": hashlib.sha256((ROOT / "docs/images" / name).read_bytes()).hexdigest(),
            }
            for name in IMAGE_NAMES
        ],
        "items": entries,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return entries


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
    verify_geometry_source()
    items = inventory()
    sheets = [composite(work, hero_items(), "hero.png", "", 2, hero=True)]
    sheets.append(
        composite(
            work,
            interface_scale_items(),
            "interface-sizes.png",
            "Unit size changes the matching local-plane interface",
            2,
        )
    )
    for filename, title, families, columns in SHEETS:
        selected = [item for family in families for item in items if item.spec.family == family]
        sheets.append(composite(work, selected, filename, title, columns))
    sheets.append(
        composite(
            work,
            bracket_assembly_items(),
            "vertical-tile-brackets.png",
            "Brackets with separate ordinary tiles",
            2,
        )
    )
    sheets.append(
        composite(
            work,
            [item for item in items if item.spec.family == "ramp"],
            "ramps.png",
            "Floor-to-mat ramps",
            3,
        )
    )
    sheets.append(
        composite(
            work,
            [item for item in items if item.spec.family == "vertical-stop"],
            "vertical-stops.png",
            "Normal full-solid vertical stops",
            3,
        )
    )
    thumbnails = thumbnail_entries(work, provenance)
    lines = [
        "# Complete attachment inventory",
        "",
        f"This page lists the {len(items)} accessories that fit the documented 350 x 320 x 325 mm build space with original joints and default settings. Each thumbnail comes from the STEP generated for that part. Other build spaces can allow different rail lengths or ramp widths.",
        "",
        "Click a thumbnail to open the full-size image. The code name beside it is the name used by the generator. Parts in one family share a scale; different families use different scales so small details stay readable. Colors only separate the shapes visually.",
        "",
        "[Back to the beginner guide](../README.md) / [Thumbnail dimensions, hashes and source provenance](images/attachments/manifest.json)",
        "",
        "Bracket names state both footprints. Deep tall is floor 1x2 -> wall 1x2, Wide low is floor 2x1 -> wall 2x1 and Deep square is floor 2x2 -> wall 2x2. Shallow tall is floor 1x1 -> wall 1x2, and Shallow wide is floor 2x1 -> wall 2x2. The two shallow IDs spell out `base..._wall...`; the original three keep their shorter IDs. Gallery examples use the standard 60 mm unit, 13 mm thickness and zero fit offset; custom matching parts use the same effective interface parameters.",
        "",
        "The individual thumbnails show the bracket alone. The [family view](images/vertical-tile-brackets.png) adds separate floor and wall tiles to show assembly; those tiles are not included in the bracket export. Deep examples show the default underside-outward wall orientation, while shallow examples show the accepted top-outward orientation. Use one orientation consistently across adjoining wall tiles because top-outward placement reverses left/right joining handedness. Holes covered by the solid backing are blind while assembled.",
        "",
        "Ramp names give width along the tile edge in unit cells. Every ramp keeps the same physical 50 mm run; width, rise and one original female pocket per cell follow its unit/thickness interface. The gallery shows standard 60/13 examples. The ramp receives a tile's north male edge and extends in positive Y. Full-height ramp joints are not available.",
        "",
        "Normal `vertical-stop` names give base X cells, base Y cells and H60/H120 shoulder height. They are filled CAD wedges with no wall holes, panel connectors or ledges. The slicer still chooses perimeters and infill.",
        "",
        "Original-style edge/corner bodies and straight rail bodies use R3. The acute rail ends use smaller complete rounds where required by fit and portable STEP checks. Plates and angled stops use R2. Brackets use R3 at the thick front-to-slope transition, R2 on other thick free edges and R1 around the thin bearing lip; normal stops and ramps keep R2. Tile joints, rail joints, bracket bearing surfaces and X attachments keep their mating geometry.",
        "",
        "Bambu projects put original brackets on their diagonal rear face, shallow brackets on a broad side, normal stops on their broad rear face and angled stops on their rear face before packing. STEP, STL and core 3MF keep model orientation. Ramps, normal stops and shallow brackets request object-level normal Auto support. Remove all support from mating regions before assembly.",
        "",
    ]
    for family, (heading, _) in FAMILIES.items():
        entries = [entry for entry in thumbnails if entry["family"] == family]
        lines += [
            f"## {heading}",
            "",
            '<table><thead><tr><th width="206">Thumbnail</th><th>Name</th><th>Size / variant</th><th>What it does</th></tr></thead><tbody>',
        ]
        for entry in entries:
            item = next(item for item in items if item.key == entry["key"])
            dims = " x ".join(f"{v:.1f}" for v in entry["size_mm"])
            public_name = escape(entry["public_name"]).replace("_", "_<wbr>")
            lines.append(
                f'<tr><td width="206">{thumbnail_tag(entry)}</td><td><code>{public_name}</code><br>Key: <code>{item.key}</code></td><td>{escape(item.detail)}<br>Bounds: {dims} mm</td><td>{escape(entry["description"])}</td></tr>'
            )
        lines += ["</tbody></table>", ""]
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
        f"Use the workbench's Python interpreter with Pillow already available; paths are supplied locally, not committed. In PowerShell, set `$env:PYTHONPATH='src'` before invoking that interpreter. The script checks geometry modules against the recorded commit, invokes STEP/inspection/render tools, then creates {len(IMAGE_NAMES)} overview PNGs and {len(items)} family-scaled thumbnails. `--compose-only` reuses verified local STEP-derived renders; `--check` verifies the committed files and their one-to-one inventory mapping without Pillow. Intermediate STEP files and raw renders remain ignored. Layout is deterministic; raster bytes can depend on graphics/Pillow versions.",
        "",
        f"Generator source revision: {revision_tag(provenance['generator_commit'])}. Generator tree: {revision_tag(provenance['generator_tree'])}. Workbench revision: {revision_tag(provenance['workbench_commit'])}.",
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
