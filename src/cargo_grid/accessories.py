"""Original accessory bodies surrounding the shared functional interfaces.

Plug accessories have their attachment shoulder at Z=0 and plugs pointing
down. Edging uses the tile's underside datum, Z=0. Physical support rails have
their upper bearing surface at Z=0 and extend down 25 mm; these are not slicer
supports and have no X-shaped attachment plugs.

Tile-facing joins reuse the shared rounded shoulder and ledge construction.
Support joins are a separate, full-height, 5 mm-deep dovetail. Their 5.085 mm
female depth is a nominal reconstruction, not a certified clearance. Support
ends 1/2/3/4 denote X/Xs/Y/Ys respectively. Non-mating outlines, reinforcement,
and lightening apertures are independently constructed, not reference contours.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import sqrt

from build123d import Axis, Face, Location, Part, Solid, Wire

from cargo_grid.interfaces import (
    dovetail_face,
    full_height_part,
    horizontal_edges,
    make_plug,
    prism,
    rectangle,
    tile_join_tool,
)
from cargo_grid.parameters import Interface, count, positive

FAMILIES = (
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
)
SUPPORT_END_NAMES = ("X", "Xs", "Y", "Ys")


@dataclass(frozen=True)
class Accessory:
    """Accessory dimensions in mm; ``nx`` counts straight edge/support cells.

    ``length`` controls support-bit length excluding its projecting join.
    ``height`` is the height above the shoulder of a lock, including its base.
    A 100 mm lock-90 2x1 provides the optional double-height configuration.
    ``variant`` selects corner and support-end types. Pitch and tile height can
    follow a custom Interface, but only reference defaults imply nominal
    reference dimensions; fixed attachment and support joins are not scaled.
    """

    family: str
    nx: int = 1
    ny: int = 1
    variant: int = 1
    length: float = 60
    height: float = 50
    interface: Interface = Interface()

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError(f"unknown accessory family: {self.family!r}")
        for name in ("nx", "ny", "variant"):
            count(name, getattr(self, name))
        positive("length", self.length)
        positive("height", self.height)
        if not isinstance(self.interface, Interface):
            raise ValueError("interface must be an Interface")
        variants = {"corner-in": 4, "corner-out": 6, "support-end": 4}
        if self.variant > variants.get(self.family, 1):
            raise ValueError(f"invalid variant for {self.family}")
        grids = {
            "plate": {(1, 1), (1, 2), (2, 2)},
            "lock-45": {(1, 1), (2, 2)},
            "lock-90": {(x, y) for x in (1, 2, 3) for y in (1, 2)},
        }
        if self.family in grids and (self.nx, self.ny) not in grids[self.family]:
            raise ValueError(f"unsupported mounting grid for {self.family}")
        if self.family not in grids and self.ny != 1:
            raise ValueError(f"{self.family} uses nx, not ny")
        if self.family in variants and self.nx != 1:
            raise ValueError(f"{self.family} uses variant, not nx")
        if self.family == "support-bit" and (self.length < 20 or self.nx != 1):
            raise ValueError("support-bit requires length >= 20 mm and nx=1")
        if self.family.startswith("lock-") and self.height < 12:
            raise ValueError("lock height must be at least 12 mm")
        if self.family == "lock-45" and self.height > self.ny * self.interface.pitch:
            raise ValueError("45-degree lock height must not exceed its base depth")


def _box(x: float, y: float, w: float, d: float, h: float, z: float = 0) -> Part:
    return prism(rectangle(x, y, w, d), h).moved(Location((0, 0, z)))


def _polygon(points: list[tuple[float, float]]) -> Face:
    return Face(Wire.make_polygon([(x, y, 0) for x, y in points], close=True))


def _join(
    x: float,
    y: float,
    angle: float,
    male: bool,
    *,
    support: bool = False,
    depth: float | None = None,
) -> dict:
    return {
        "position": (x, y, -25 if support else 0),
        "angle": angle,
        "sex": "male" if male else "female",
        "depth": depth
        if depth is not None
        else ((5 if male else 5.085) if support else (6 if male else 6.1)),
        "height": 25 if support else (10 if male else 10.2),
        "interface": "support-dovetail" if support else "tile-dovetail",
    }


def _edge_plan(spec: Accessory) -> tuple[Face, list[dict]]:
    p = spec.interface.pitch
    if spec.family in ("edge-x", "edge-y"):
        male = spec.family == "edge-x"
        return rectangle(0, -10 if male else 0, spec.nx * p, 10), [
            _join((i + 0.5) * p, 0, 0, male) for i in range(spec.nx)
        ]
    if spec.family == "corner-in":
        # Square internal elbows replace the source's curved non-mating web.
        v = spec.variant
        right, top = v in (2, 3), v in (1, 2)
        vertical = rectangle(p - 10 if right else 0, 0, 10, p)
        horizontal = rectangle(0, p - 10 if top else 0, p, 10)
        face = Face(vertical.fuse(horizontal).faces()[0].wrapped)
        return face, [
            _join(p if right else 0, p / 2, -90, right),
            _join(p / 2, p if top else 0, 0, top),
        ]
    v = spec.variant
    if v in (3, 6):
        if v == 3:
            face = _polygon(
                [
                    (0, p),
                    (p, p),
                    (p, 0),
                    (p + 10, 0),
                    (p + 10, p + 10),
                    (0, p + 10),
                ]
            )
            joins = [_join(p, p / 2, -90, False), _join(p / 2, p, 0, False)]
        else:
            face = _polygon(
                [
                    (-10, -10),
                    (p, -10),
                    (p, 0),
                    (0, 0),
                    (0, p),
                    (-10, p),
                ]
            )
            joins = [_join(0, p / 2, -90, True), _join(p / 2, 0, 0, True)]
        return face, joins
    extension = 5 * sqrt(2)
    male = v in (1, 5)
    # Preserve the diagonal butt datum, using a straight bevel outside it.
    if v in (2, 5):
        if v == 5:
            points = [(0, -10), (p, -10), (p + extension, -extension), (p, 0), (0, 0)]
        else:
            points = [(-extension, extension), (0, 0), (p, 0), (p, 10), (0, 10)]
        return _polygon(points), [_join(p / 2, 0, 0, male)]
    if v == 1:
        points = [(-10, 0), (0, 0), (0, p), (-extension, p + extension), (-10, p)]
    else:
        points = [(0, 0), (extension, -extension), (10, 0), (10, p), (0, p)]
    return _polygon(points), [_join(0, p / 2, -90, male)]


def _join_solid(join: dict, *, interface: Interface = Interface()) -> Part:
    if join["interface"] == "tile-dovetail":
        tool = tile_join_tool(interface, depth=join["depth"], male=join["sex"] == "male")
    else:
        face = dovetail_face(depth=join["depth"])
        face = face.fillet_2d(1, face.vertices())
        tool = prism(face, join["height"])
        for x in (-26.5, 22.5):
            tool = tool.cut(_box(x, -5, 4, join["depth"] + 6, 27, -1))
    return tool.rotate(Axis.Z, join["angle"]).moved(Location(join["position"]))


def _apply_joins(part: Part, joins: list[dict], *, interface: Interface = Interface()) -> Part:
    for join in joins:
        tool = _join_solid(join, interface=interface)
        part = part.fuse(tool) if join["sex"] == "male" else part.cut(tool)
    return part.clean()


@lru_cache(maxsize=1)
def _downward_plug() -> Part:
    return make_plug().rotate(Axis.X, 180)


def _mount_centers(spec: Accessory) -> list[tuple[float, float, float]]:
    p = spec.interface.pitch
    return [((x + 0.5) * p, (y + 0.5) * p, 0) for x in range(spec.nx) for y in range(spec.ny)]


def _cross_prism(points: list[tuple[float, float]], width: float, x: float = 0) -> Part:
    face = Face(Wire.make_polygon([(x, y, z) for y, z in points], close=True))
    return Part(Solid.extrude(face, (width, 0, 0)).wrapped)


def _mounted(spec: Accessory) -> Part:
    w, d = spec.nx * spec.interface.pitch, spec.ny * spec.interface.pitch
    base_height = 4.1
    part = _box(0, 0, w, d, base_height)
    part = part.fillet(1, horizontal_edges(part, base_height))
    centers = _mount_centers(spec)
    for center in centers:
        part = part.fuse(_downward_plug().moved(Location(center)))
    roots = [
        edge
        for edge in horizontal_edges(part, 0)
        if any(
            abs(edge.center().X - x) < 23 and abs(edge.center().Y - y) < 23 for x, y, _ in centers
        )
    ]
    part = part.fillet(2 if spec.family == "plate" else 1, roots)
    if spec.family != "plate":
        rise = spec.height - base_height
        lean = rise if spec.family == "lock-45" else 0
        wall_points = [(d - 6, base_height - 1), (d, base_height - 1)]
        if lean:
            wall_points.append((d, base_height))
        wall_points.extend([(d - lean, spec.height), (d - lean - 6, spec.height)])
        if lean:
            wall_points.append((d - 6, base_height))
        wall = _cross_prism(wall_points, w)
        part = part.fuse(wall)
        reach = max(18, lean)
        for x in (0, w - 4):
            part = part.fuse(
                _cross_prism(
                    [
                        (max(0, d - 6 - reach), base_height - 1),
                        (d - 3, base_height - 1),
                        (d - lean - 3, spec.height - 3),
                    ],
                    4,
                    x,
                )
            )
    return part.clean()


def _support_plan(spec: Accessory) -> tuple[float, list[dict]]:
    if spec.family == "support-end":
        male = spec.variant in (3, 4)
        return 2 * spec.interface.pitch, [
            _join(
                0,
                0 if male else 2 * spec.interface.pitch,
                180,
                male,
                support=True,
            )
        ]
    length = spec.length if spec.family == "support-bit" else spec.nx * spec.interface.pitch
    return length, [
        _join(0, 0, 180, True, support=True),
        _join(0, length, 180, False, support=True),
    ]


def _support(spec: Accessory) -> Part:
    length, joins = _support_plan(spec)
    if spec.family == "support-end":
        ramp = 55 if spec.variant in (2, 4) else 75
        if spec.variant in (1, 2):
            points = [(0, -12), (ramp, -25), (length, -25), (length, 0), (0, 0)]
        else:
            points = [(0, -25), (length - ramp, -25), (length, -12), (length, 0), (0, 0)]
        part = _cross_prism(points, 45, -22.5)
    else:
        part = _box(-22.5, 0, 45, length, 25, -25)
    # Original rectangular windows leave a 12.5 mm bearing rail on either side.
    for start in range(0, int(length) - 35, 60):
        span = min(32, length - start - 24)
        if span >= 12:
            part = part.cut(_box(-10, start + 12, 20, span, 27, -26))
    return _apply_joins(part, joins)


def accessory_datums(spec: Accessory) -> dict:
    """Machine-readable nominal mating datums; no physical-fit assertions."""
    if spec.family in ("plate", "lock-90", "lock-45"):
        return {
            "shoulder_z": 0,
            "plug_tip_z": -12.8,
            "mount_centers": _mount_centers(spec),
            "joins": [],
        }
    if spec.family.startswith("support"):
        length, joins = _support_plan(spec)
        result = {
            "bearing_z": 0,
            "underside_z": -25,
            "body_length": length,
            "mount_centers": [],
            "joins": joins,
        }
        if spec.family == "support-end":
            result.update(
                end=SUPPORT_END_NAMES[spec.variant - 1],
                ramp_length=55 if spec.variant in (2, 4) else 75,
                ramp_rise=13,
            )
        return result
    _, joins = _edge_plan(spec)
    for join in joins:
        join["joint_style"] = spec.interface.joint_style
        join["height"] = (
            spec.interface.male_height
            if join["sex"] == "male"
            else spec.interface.female_opening_height
        )
        join["open_through_top"] = (
            join["sex"] == "female" and spec.interface.joint_style == "full-height"
        )
    return {"underside_z": 0, "top_z": spec.interface.height, "mount_centers": [], "joins": joins}


def make_accessory(spec: Accessory) -> Part:
    """Build one connected, labeled accessory without changing print orientation."""
    if not isinstance(spec, Accessory):
        raise ValueError("spec must be an Accessory")
    if spec.family in ("plate", "lock-90", "lock-45"):
        part = _mounted(spec)
    elif spec.family.startswith("support"):
        part = _support(spec)
    else:
        face, joins = _edge_plan(spec)
        if spec.interface.joint_style == "full-height":
            males, females = [], []
            for join in joins:
                profile = dovetail_face(depth=join["depth"]).rotate(Axis.Z, join["angle"])
                profile = profile.moved(Location(join["position"]))
                (males if join["sex"] == "male" else females).append(profile)
            part = full_height_part(
                face, males, females, spec.interface.height, round_body_corners=False
            )
        else:
            part = _apply_joins(prism(face, spec.interface.height), joins, interface=spec.interface)
        part = part.fillet(1, horizontal_edges(part, 0))
    suffix = (
        f"{spec.nx}x{spec.ny}"
        if spec.family in ("plate", "lock-90", "lock-45")
        else f"v{spec.variant}"
        if spec.family in ("corner-in", "corner-out", "support-end")
        else f"{spec.length:g}mm"
        if spec.family == "support-bit"
        else str(spec.nx)
    )
    part.label = f"{spec.family}_{suffix}"
    if spec.family.startswith("lock-"):
        part.label += f"_h{spec.height:g}"
    part.label += f"_{spec.interface.joint_style}"
    if not part.is_valid or len(part.solids()) != 1 or part.volume <= 0:
        raise ValueError(f"{part.label}: invalid or disconnected geometry")
    return part
