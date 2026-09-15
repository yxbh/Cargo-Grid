"""One shared, explicit command-line interface for parts, layouts and catalogues."""

import argparse
import json
import sys
from math import floor
from pathlib import Path

from cargo_grid._version import __version__
from cargo_grid.accessories import Accessory
from cargo_grid.catalogue import accessory_design, catalogue_job
from cargo_grid.export import BambuSettings, Material, export_job
from cargo_grid.jobs import Job, layout_job, tile_design
from cargo_grid.layout import exact_layout
from cargo_grid.parameters import BuildVolume, Exclusion, Interface, Tile, count, positive
from cargo_grid.roof_support import RoofSupportSettings
from cargo_grid.stacking import StackSettings


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Parametric cargo mats: STEP-first geometry and unsliced print-job exports.",
        epilog="Original roofed joints; optional holes and roof supports are off by default. No slicing or printer control.",
    )
    root.add_argument("--version", action="version", version=f"cargo-grid {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    descriptions = {
        "part": "Generate one tile or accessory design with an explicit quantity.",
        "layout": "Fill an exact rectangular footprint with full-pitch tiles and integrated fillers.",
        "catalogue": "Generate every supported ordered tile size that fits, plus the finite accessory catalogue.",
    }
    for command in ("part", "layout", "catalogue"):
        p = commands.add_parser(
            command,
            help=descriptions[command],
            description=descriptions[command],
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        p.add_argument("--build", type=float, nargs=3, required=True, metavar=("X", "Y", "Z"))
        p.add_argument("--margin", type=float, default=0)
        p.add_argument(
            "--part-gap", type=float, default=2, help="catalogue packing separation in mm"
        )
        p.add_argument("--reserve", type=float, nargs=3, default=(0, 0, 0), metavar=("X", "Y", "Z"))
        p.add_argument(
            "--exclude",
            type=float,
            nargs=4,
            action="append",
            default=[],
            metavar=("X", "Y", "WIDTH", "DEPTH"),
        )
        p.add_argument("--pitch", type=float, default=60)
        p.add_argument("--height", type=float, default=13)
        p.add_argument(
            "--joint-style",
            choices=("original", "full-height"),
            default="original",
            help="original roofed joints (default), or experimental full-height tabs/open pockets",
        )
        p.add_argument(
            "--fit-offset",
            type=float,
            default=0,
            help="socket offset in mm; nonzero changes the compatibility preset",
        )
        p.add_argument(
            "--holes", action="store_true", help="enable optional round holes with --hole-diameter"
        )
        p.add_argument(
            "--hole-diameter", type=float, help="required when enabling optional round holes"
        )
        p.add_argument(
            "--hole-scope",
            choices=("interior", "full"),
            default="interior",
            help="interior holes (default), or explicit edge/corner lattice on retained joining edges",
        )
        p.add_argument("--output", type=Path, required=True, help="new or empty job directory")
        p.add_argument("--no-stl", action="store_true")
        p.add_argument(
            "--bambu", action="store_true", help="unsliced project, not calibrated print settings"
        )
        p.add_argument(
            "--material", action="append", nargs=3, default=[], metavar=("LABEL", "TYPE", "#RRGGBB")
        )
        p.add_argument("--nozzle", type=float, help="explicit diagnostic project setting, mm")
        p.add_argument("--layer-height", type=float, help="explicit diagnostic project setting, mm")
        p.add_argument(
            "--roof-support",
            action="store_true",
            help="Bambu manual supports under retained west/south female pocket roofs; PETG slot 1 / PLA slot 2",
        )
        p.add_argument(
            "--roof-top-gap", type=float, help="explicit experimental support-to-roof Z gap, mm"
        )
        p.add_argument("--roof-interface-layers", type=int)
        p.add_argument(
            "--roof-coverage",
            choices=("critical", "full"),
            help="critical pads (default when roof support is enabled) or conservative full roof",
        )
        p.add_argument(
            "--roof-interface-spacing", type=float, help="explicit interface line spacing, mm"
        )
        p.add_argument(
            "--roof-nozzles",
            type=int,
            nargs=2,
            metavar=("PETG", "PLA"),
            help="optional Custom physical nozzle assignment; omit for native automatic slice mode",
        )
        p.add_argument(
            "--roof-foot-expansion",
            type=float,
            help="support first-layer expansion in mm; omit or -1 for native auto, 0 disables it",
        )
        p.add_argument(
            "--stack-count", help="maximum identical tiles per batch: positive integer or auto"
        )
        p.add_argument("--stack-gap", type=float)
        p.add_argument("--interface-thickness", type=float)
        p.add_argument(
            "--material-roles",
            type=int,
            nargs=3,
            metavar=("MODEL", "SUPPORT_BASE", "RELEASE_INTERFACE"),
        )
        if command == "part":
            p.add_argument(
                "--family",
                default="tile",
                choices=[
                    "tile",
                    "edge-x",
                    "edge-y",
                    "corner-in",
                    "corner-out",
                    "lock-90",
                    "lock-45",
                    "plate",
                    "support",
                    "support-bit",
                    "support-end",
                ],
            )
            p.add_argument("--cells", type=int, nargs=2, default=(1, 1), metavar=("X", "Y"))
            p.add_argument("--variant", type=int, default=1)
            p.add_argument("--length", type=float, default=60)
            p.add_argument("--accessory-height", type=float, default=50)
            p.add_argument("--quantity", type=int, default=1)
        if command == "layout":
            p.add_argument(
                "--footprint", type=float, nargs=2, required=True, metavar=("WIDTH", "DEPTH")
            )
            p.add_argument(
                "--filler", choices=["balanced", "positive", "negative"], default="balanced"
            )
    compare = commands.add_parser(
        "compare-reference",
        help="Compare measured interfaces with an explicitly supplied local reference; no upload.",
    )
    compare.add_argument("reference", type=Path, help="explicit local 3MF, never uploaded")
    compare.add_argument(
        "--output", type=Path, required=True, help="new JSON report path; never overwritten"
    )
    return root


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command == "compare-reference":
            from cargo_grid.validation import compare_reference

            if args.output.exists():
                raise ValueError(f"output file already exists: {args.output}; choose a new path")
            result = compare_reference(args.reference)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as output:
                output.write(json.dumps(result, indent=2) + "\n")
            print(
                f"reference comparison (joint-style original): {'PASS' if result['checked_pass'] else 'FAIL'}; {args.output}"
            )
            return 0 if result["checked_pass"] else 1
        if args.holes != (args.hole_diameter is not None):
            raise ValueError("enable holes with BOTH --holes and an explicit --hole-diameter")
        if args.hole_scope == "full" and not args.holes:
            raise ValueError("--hole-scope full requires --holes and --hole-diameter")
        build = BuildVolume(
            *args.build,
            margin=args.margin,
            reserve_x=args.reserve[0],
            reserve_y=args.reserve[1],
            reserve_z=args.reserve[2],
            exclusions=tuple(Exclusion(*a) for a in args.exclude),
        )
        interface = Interface(args.pitch, args.height, args.fit_offset, args.joint_style)
        roof_support = None
        roof_values = (
            args.roof_top_gap,
            args.roof_interface_layers,
            args.roof_interface_spacing,
        )
        if (
            args.roof_support
            or any(v is not None for v in roof_values)
            or args.roof_coverage is not None
            or args.roof_nozzles is not None
            or args.roof_foot_expansion is not None
        ):
            if not args.roof_support or not all(v is not None for v in roof_values):
                raise ValueError(
                    "roof supports require --roof-support, --roof-top-gap, --roof-interface-layers and --roof-interface-spacing"
                )
            if not args.bambu:
                raise ValueError(
                    "roof supports require --bambu; core 3MF has no native support semantics"
                )
            if args.joint_style != "original":
                raise ValueError("roof supports require original roofed joints")
            if args.command == "catalogue" or (args.command == "part" and args.family != "tile"):
                raise ValueError("roof supports require a tile-only part or layout job")
            if any(
                v is not None
                for v in (
                    args.stack_count,
                    args.stack_gap,
                    args.interface_thickness,
                    args.material_roles,
                )
            ):
                raise ValueError("roof supports and stacked separator jobs cannot be combined")
            roof_support = RoofSupportSettings(
                args.roof_top_gap,
                args.roof_interface_layers,
                args.roof_interface_spacing,
                tuple(args.roof_nozzles) if args.roof_nozzles is not None else None,
                coverage=args.roof_coverage or "critical",
                foot_expansion=args.roof_foot_expansion,
            )
        bambu = None
        if args.bambu:
            if args.nozzle is None or args.layer_height is None:
                raise ValueError("Bambu export requires explicit --nozzle and --layer-height")
            bambu = BambuSettings(
                tuple(Material(*m) for m in args.material),
                args.nozzle,
                args.layer_height,
                roof_support=roof_support,
            )
        elif args.material or args.nozzle or args.layer_height:
            raise ValueError("material/nozzle/layer settings require --bambu")
        stack = None
        supplied = (args.stack_count, args.stack_gap, args.interface_thickness, args.material_roles)
        if any(v is not None for v in supplied):
            if not all(v is not None for v in supplied) or not bambu:
                raise ValueError(
                    "stacking requires --bambu, count, gap, interface thickness and material roles"
                )
            if args.command == "catalogue":
                raise ValueError(
                    "stack repeated part/layout quantities, not mixed catalogue samples"
                )
            if args.command == "part" and args.family != "tile":
                raise ValueError("stacking is restricted to identical tile quantities")
            positive("stack gap", args.stack_gap)
            stack_count = (
                floor(
                    (build.usable[2] + args.stack_gap + 1e-8) / (interface.height + args.stack_gap)
                )
                if args.stack_count == "auto"
                else int(args.stack_count)
            )
            stack = StackSettings(
                stack_count, args.stack_gap, args.interface_thickness, *args.material_roles
            )
        if args.command == "part":
            count("quantity", args.quantity)
            if args.family == "tile":
                design = tile_design(
                    Tile(*args.cells, interface, args.hole_diameter, hole_scope=args.hole_scope)
                )
            else:
                if args.holes:
                    raise ValueError("optional web holes apply to tiles, not accessory bodies")
                design = accessory_design(
                    Accessory(
                        args.family,
                        *args.cells,
                        args.variant,
                        args.length,
                        args.accessory_height,
                        interface,
                    )
                )
            design.quantity = args.quantity
            if build.placement(design.size) is None:
                raise ValueError(f"actual part bounds {design.size} exceed usable print area")
            job = Job([design], build, "part")
        elif args.command == "layout":
            layout = exact_layout(
                *args.footprint,
                build,
                interface=interface,
                distribution=args.filler,
                hole_diameter=args.hole_diameter,
                hole_scope=args.hole_scope,
            )
            job = layout_job(layout, build)
        else:
            job = catalogue_job(
                build,
                interface=interface,
                hole_diameter=args.hole_diameter,
                hole_scope=args.hole_scope,
            )
        job.part_gap = args.part_gap
        manifest = export_job(job, args.output, stl=not args.no_stl, bambu=bambu, stack=stack)
        print(manifest)
        rejected = sum(not h["accepted"] for d in job.designs for h in d.holes)
        if rejected:
            print(
                f"WARNING: {rejected} optional hole placements rejected by keep-outs; see manifest.",
                file=sys.stderr,
            )
        if job.omitted:
            print(
                f"WARNING: {len(job.omitted)} oversized accessories omitted; see manifest.",
                file=sys.stderr,
            )
        geometry_warning = interface.compatibility()["geometry_warning"]
        if geometry_warning and (args.command != "part" or args.family == "tile"):
            print(f"WARNING: {geometry_warning}", file=sys.stderr)
        if roof_support:
            print(
                "WARNING: Native roof supports are uncalibrated dual-material requests. "
                "Generated support may temporarily cross edge round cutouts; remove from the underside before assembly. "
                "Verify nozzle assignments, sliced support paths and physical release.",
                file=sys.stderr,
            )
        print(
            "Generated geometry is not a print preset: inspect slicer output and verify physical fit separately.",
            file=sys.stderr,
        )
        return 0
    except (ValueError, OSError) as error:
        p.exit(2, f"cargo-grid: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
