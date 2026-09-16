"""Finite functional catalogue bounded by the user's usable print envelope."""

import json
from dataclasses import asdict
from hashlib import sha256
from math import floor
from typing import Literal

from cargo_grid.accessories import (
    BAMBU_OBJECT_SETTINGS,
    VERTICAL_BRACKET_CELLS,
    VERTICAL_STOP_CELLS,
    VERTICAL_STOP_HEIGHTS_MM,
    Accessory,
    bambu_print_rotation,
    make_accessory,
)
from cargo_grid.jobs import Design, Job, tile_design
from cargo_grid.parameters import BuildVolume, Interface, Tile


def tile_sizes(build: BuildVolume, interface: Interface = Interface()) -> list[tuple[int, int]]:
    longest = max(build.usable[:2])
    maximum = max(0, floor((longest - 6 + 1e-6) / interface.pitch))
    return [
        (x, y)
        for x in range(1, maximum + 1)
        for y in range(1, maximum + 1)
        if build.placement((x * interface.pitch + 6, y * interface.pitch + 6, interface.height))
        is not None
    ]


def accessory_variants(build: BuildVolume, interface: Interface = Interface()) -> list[Accessory]:
    nmax = max(1, floor(max(build.usable[:2]) / interface.pitch))
    result = []
    for n in range(1, nmax + 1):
        result.extend(
            Accessory(family, nx=n, interface=interface)
            for family in ("edge-x", "edge-y", "support")
        )
    result.extend(Accessory("corner-in", variant=v, interface=interface) for v in range(1, 5))
    result.extend(Accessory("corner-out", variant=v, interface=interface) for v in range(1, 7))
    result.extend(Accessory("support-end", variant=v, interface=interface) for v in range(1, 5))
    result.extend(
        Accessory("support-bit", length=length, interface=interface) for length in (20, 30, 40, 50)
    )
    if interface.reference_socket_dimensions:
        result.extend(
            Accessory("vertical-tile-bracket", nx=x, ny=y, interface=interface)
            for x, y in VERTICAL_BRACKET_CELLS
        )
    result.extend(
        Accessory("vertical-stop", nx=x, ny=y, height=height, interface=interface)
        for x, y in VERTICAL_STOP_CELLS
        for height in VERTICAL_STOP_HEIGHTS_MM
    )
    result.extend(
        Accessory("lock-45", nx=x, ny=y, interface=interface) for x, y in ((1, 1), (2, 2))
    )
    result.extend(
        Accessory("plate", nx=x, ny=y, interface=interface) for x, y in ((1, 1), (1, 2), (2, 2))
    )
    return result


def accessory_design(spec: Accessory) -> Design:
    parameters = asdict(spec)
    token = sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:10]
    dimensions = (
        f"{spec.nx}x{spec.ny}_h{spec.height:g}"
        if spec.family == "vertical-stop"
        else f"{spec.nx}x{spec.ny}"
    )
    name = f"{spec.family}_{dimensions}_v{spec.variant}_{spec.interface.joint_style}_{token}"
    shape = make_accessory(spec)
    shape.label = name
    rotation = bambu_print_rotation(spec)
    return Design(
        name,
        shape,
        parameters,
        recommended_print_rotation_x=rotation,
        apply_orientation_to_bambu=rotation is not None,
        bambu_object_settings=dict(BAMBU_OBJECT_SETTINGS.get(spec.family, {})),
    )


def catalogue_job(
    build: BuildVolume,
    *,
    interface: Interface = Interface(),
    hole_diameter: float | None = None,
    hole_scope: Literal["interior", "full"] = "interior",
    orient_for_bambu: bool = False,
) -> Job:
    designs = [
        tile_design(Tile(x, y, interface, hole_diameter, hole_scope=hole_scope))
        for x, y in tile_sizes(build, interface)
    ]
    omitted = []
    for spec in accessory_variants(build, interface):
        design = accessory_design(spec)
        size = design.bambu_size if orient_for_bambu else design.size
        if build.placement(size) is None:
            omitted.append(
                {
                    "name": design.name,
                    "parameters": design.parameters,
                    "size_mm": size,
                    "reason": "actual bounds exceed usable envelope",
                }
            )
        else:
            designs.append(design)
    for design in designs:
        if build.placement(design.bambu_size if orient_for_bambu else design.size) is None:
            raise ValueError(f"unexpected actual-bounds fit failure: {design.name}")
    if not designs:
        raise ValueError("no supported designs fit the configured build envelope")
    return Job(designs, build, "catalogue", omitted=omitted)
