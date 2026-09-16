"""Part identity, quantities and assembly frames shared by all CLI commands."""

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import isfinite

from build123d import Axis, Part

from cargo_grid.layout import Layout
from cargo_grid.parameters import BuildVolume, Tile, count, positive
from cargo_grid.tiles import hole_placements, make_tile


@dataclass
class Design:
    name: str
    shape: Part
    parameters: dict
    quantity: int = 1
    assembly_frames: list[tuple[float, float, float]] = field(default_factory=list)
    holes: list[dict] = field(default_factory=list)
    recommended_print_rotation_x: float | None = None
    apply_orientation_to_bambu: bool = False

    def __post_init__(self):
        count("design quantity", self.quantity)
        if self.recommended_print_rotation_x is not None and not isfinite(
            self.recommended_print_rotation_x
        ):
            raise ValueError("recommended print rotation must be finite degrees")
        if not isinstance(self.apply_orientation_to_bambu, bool):
            raise ValueError("apply_orientation_to_bambu must be a boolean")
        if self.apply_orientation_to_bambu and self.recommended_print_rotation_x is None:
            raise ValueError("Bambu orientation requires an explicit recommended rotation")

    @property
    def size(self) -> tuple[float, float, float]:
        box = self.shape.bounding_box()
        return tuple(box.size)

    @property
    def bambu_shape(self) -> Part:
        if self.apply_orientation_to_bambu:
            assert self.recommended_print_rotation_x is not None
            return self.shape.rotate(Axis.X, self.recommended_print_rotation_x)
        return self.shape

    @property
    def bambu_size(self) -> tuple[float, float, float]:
        return tuple(self.bambu_shape.bounding_box().size)


@dataclass
class Job:
    designs: list[Design]
    build: BuildVolume
    kind: str
    omitted: list[dict] = field(default_factory=list)
    footprint: tuple[float, float] | None = None
    part_gap: float = 2

    def __post_init__(self):
        if not self.designs:
            raise ValueError("a job needs at least one design")
        positive("part gap", self.part_gap, zero=True)


def tile_design(tile: Tile) -> Design:
    parameters = asdict(tile)
    token = sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:10]
    scope = f"_{tile.hole_scope}-holes" if tile.hole_diameter is not None else ""
    name = f"tile_{tile.nx}x{tile.ny}_{tile.interface.joint_style}{scope}_{token}"
    shape = make_tile(tile)
    shape.label = name
    return Design(name, shape, parameters, holes=[asdict(h) for h in hole_placements(tile)])


def layout_job(layout: Layout, build: BuildVolume) -> Job:
    designs: dict[Tile, Design] = {}
    for placed in layout.pieces:
        if placed.tile not in designs:
            designs[placed.tile] = tile_design(placed.tile)
            designs[placed.tile].quantity = 0
        design = designs[placed.tile]
        if build.placement(design.size) is None:
            raise ValueError(f"actual exported candidate {design.name} does not fit")
        design.quantity += 1
        design.assembly_frames.append((placed.x, placed.y, 0))
    return Job(list(designs.values()), build, "layout", footprint=(layout.width, layout.depth))
