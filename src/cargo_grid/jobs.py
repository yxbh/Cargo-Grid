"""Part identity, quantities and assembly frames shared by all CLI commands."""

import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256

from build123d import Part

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

    def __post_init__(self):
        count("design quantity", self.quantity)

    @property
    def size(self) -> tuple[float, float, float]:
        box = self.shape.bounding_box()
        return tuple(box.size)


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
