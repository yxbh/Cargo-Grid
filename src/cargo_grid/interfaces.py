"""Analytic functional interfaces, independently defined from scalar measurements.

The lower-left body corner is the tile datum. Socket centres are half a pitch
from it. Z=0 is the underside; the attachment shoulder seats at tile height.
"""

from functools import lru_cache
from math import sqrt

from build123d import Axis, Edge, Face, Location, Part, Plane, Solid, Vector, Wire
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet
from OCP.Standard import Standard_Failure
from OCP.StdFail import StdFail_NotDone

from cargo_grid.parameters import Interface


def x_profile(*, plug: bool = False, offset: float = 0.0) -> Face:
    """Four round lobes and four concave necks joined by diagonal tangents."""
    lobe = 14.344 if plug else 14.5
    radius = 7.85556 if plug else 5.5 * sqrt(2)
    neck_radius = 6.214 if plug else 4.5 * sqrt(2)
    neck_center = (radius + neck_radius) * sqrt(2)
    a = neck_radius / sqrt(2)
    b = radius / sqrt(2)
    points = [
        (neck_center - a, a),
        (lobe + b, lobe - b),
        (lobe + radius / sqrt(2), lobe + radius / sqrt(2)),
        (lobe - b, lobe + b),
        (a, neck_center - a),
        (0, neck_center - neck_radius),
        (-a, neck_center - a),
    ]

    def rotate(p: tuple[float, float], turn: int) -> Vector:
        x, y = p
        for _ in range(turn):
            x, y = -y, x
        return Vector(x, y, 0)

    edges = []
    for turn in range(4):
        p = [rotate(v, turn) for v in points]
        edges.extend(
            [
                Edge.make_line(p[0], p[1]),
                Edge.make_three_point_arc(p[1], p[2], p[3]),
                Edge.make_line(p[3], p[4]),
                Edge.make_three_point_arc(p[4], p[5], p[6]),
            ]
        )
    face = Face(Wire(edges))
    if offset:
        face = Face(face.outer_wire().offset_2d(offset))
    return face


def prism(face: Face, height: float) -> Part:
    return Part([Solid.extrude(face, (0, 0, height))])


def rectangle(x: float, y: float, width: float, depth: float) -> Face:
    return Face(
        Wire.make_polygon(
            [(x, y, 0), (x + width, y, 0), (x + width, y + depth, 0), (x, y + depth, 0)], close=True
        )
    )


def dovetail_face(*, depth: float = 6.0) -> Face:
    """Sharp tool, extending outside a boundary to make the root blend possible."""
    head = 11.5 + depth
    return Face(
        Wire.make_polygon(
            [
                (-25, -4, 0),
                (25, -4, 0),
                (25, 0, 0),
                (11.5, 0, 0),
                (head, depth, 0),
                (-head, depth, 0),
                (-11.5, 0, 0),
                (-25, 0, 0),
            ],
            close=True,
        )
    )


def horizontal_edges(shape: Part, z: float, tolerance: float = 1e-5) -> list[Edge]:
    return [
        edge
        for edge in shape.edges()
        if abs(edge.bounding_box().min.Z - z) < tolerance
        and abs(edge.bounding_box().max.Z - z) < tolerance
    ]


def underside_fillet(shape: Part) -> Solid:
    """Repair OCCT's shared-vertex topology after solving a large perimeter."""
    operation = BRepFilletAPI_MakeFillet(shape.wrapped)
    for edge in horizontal_edges(shape, 0):
        operation.Add(1.0, edge.wrapped)
    try:
        result = Solid(operation.Shape()).fix()
    except (Standard_Failure, StdFail_NotDone) as error:
        raise ValueError("could not solve the 1 mm underside fillet") from error
    if not result.is_valid or len(result.solids()) != 1:
        raise ValueError("underside fillet remained invalid after kernel topology repair")
    return result


def joining_tool(*, depth: float = 6, ledge: float = 10, height: float = 13) -> Part:
    """Wall plus rounded dovetail, solving shared corner blends simultaneously."""
    wall = prism(rectangle(-25, -4, 50, 4), height)
    shape = wall.fuse(prism(dovetail_face(depth=depth), ledge))
    shape = shape.fillet(1, list(shape.edges().filter_by(Axis.Z)) + horizontal_edges(shape, ledge))
    return shape.fillet(1, horizontal_edges(shape, height))


def tile_join_tool(interface: Interface, *, depth: float = 6, male: bool) -> Part:
    """Consistent tile/edging join: original roof or full-height open pocket."""
    if interface.joint_style == "original":
        return joining_tool(
            depth=depth,
            ledge=interface.male_height if male else interface.female_opening_height,
            height=interface.height,
        )
    face = dovetail_face(depth=depth)
    face = face.fillet_2d(1, face.vertices())
    if not male:
        return prism(face, interface.height + 2).moved(Location((0, 0, -1)))
    shape = prism(face, interface.height)
    return shape.fillet(1, horizontal_edges(shape, interface.height))


def full_height_part(
    body: Face,
    male_faces: list[Face],
    female_faces: list[Face],
    height: float,
    *,
    round_body_corners: bool = True,
    free_top_rims: list[tuple[str, float]] | None = None,
    free_top_radius: float = 2.0,
) -> Part:
    """Build roofless joints in the planar outline, avoiding coincident 3D cuts."""
    outline = body
    if male_faces:
        outline = outline.fuse(*male_faces)
    if female_faces:
        outline = outline.cut(*female_faces)
    if len(outline.faces()) != 1:
        raise ValueError("full-height edge outline must remain connected")
    face = outline.faces()[0]
    vertices = list(face.vertices())
    if not round_body_corners:
        vertices = [
            v
            for v in vertices
            if all(v.distance_to(original) > 1e-6 for original in body.vertices())
        ]
    if vertices:
        face = face.fillet_2d(1, vertices)
    part = prism(face, height)
    if free_top_rims is not None:
        operation = BRepFilletAPI_MakeFillet(part.wrapped)
        selected = 0
        for edge in horizontal_edges(part, height):
            box = edge.bounding_box()
            free = any(
                abs(getattr(box.min, axis) - coordinate) < 1e-5
                and abs(getattr(box.max, axis) - coordinate) < 1e-5
                for axis, coordinate in free_top_rims
            )
            selected += free
            operation.Add(free_top_radius if free else 1.0, edge.wrapped)
        if not selected:
            raise ValueError("full-height accessory has no selected free top rims")
        try:
            rounded = Part(Solid(operation.Shape()).wrapped)
        except (Standard_Failure, StdFail_NotDone) as error:
            raise ValueError("could not solve selective full-height top radii") from error
        if not rounded.is_valid or len(rounded.solids()) != 1:
            raise ValueError("selective full-height top rounding produced invalid geometry")
        return rounded
    return part.fillet(1, horizontal_edges(part, height))


@lru_cache(maxsize=16)
def socket_entry_tool(height: float, fit_offset: float) -> Part:
    """Preserve the 3 mm entry roundover even where open edge pockets meet it."""
    profile = x_profile(offset=fit_offset)
    carrier = prism(rectangle(-35, -35, 70, 70), height + 1).moved(Location((0, 0, -1)))
    bore = prism(profile, height + 3).moved(Location((0, 0, -2)))
    material = carrier.cut(bore)
    rim = profile.outer_wire().moved(Location((0, 0, height)))
    material = material.fillet(
        3,
        [
            edge
            for edge in horizontal_edges(material, height)
            if rim.distance_to(edge.center()) < 1e-5
        ],
    )
    return Part(carrier.cut(material).solids())


def make_plug() -> Part:
    plug = prism(x_profile(plug=True), 12.8)
    return plug.fillet(2, horizontal_edges(plug, 12.8))


def section_face(shape: Part, z: float) -> Face:
    from build123d import section

    faces = section(shape, section_by=Plane.XY.offset(z)).faces()
    if len(faces) != 1:
        raise ValueError(f"expected one section face at z={z}, got {len(faces)}")
    return faces[0]
