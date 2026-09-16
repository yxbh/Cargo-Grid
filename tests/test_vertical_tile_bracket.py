"""Approved reference-space geometry, not a physical load or fit certification."""

from dataclasses import replace

import pytest
from build123d import Axis, GeomType, Location, Part, Solid, Vector, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface

from cargo_grid import BuildVolume, Interface, Tile, make_tile
from cargo_grid.accessories import (
    VERTICAL_BRACKET_CELLS,
    Accessory,
    _mounted_base,
    _vertical_bracket,
    accessory_datums,
    make_accessory,
)
from cargo_grid.catalogue import accessory_design, accessory_variants
from cargo_grid.interfaces import make_plug


def volume(shape):
    return sum(s.volume for s in shape.solids()) if shape and shape.solids() else 0


def difference(a, b):
    return volume(a.cut(b)) + volume(b.cut(a))


def clipped(shape, x, y, z, width, depth, height):
    box = Solid.make_box(width, depth, height).moved(Location((x, y, z)))
    return Part(shape.intersect(box).solids())


def contact_faces(shape, z, sign):
    return [
        f
        for f in shape.faces()
        if f.geom_type == GeomType.PLANE
        and sign * f.normal_at().Z > 0.99
        and abs(f.bounding_box().min.Z - z) < 1e-5
        and abs(f.bounding_box().max.Z - z) < 1e-5
    ]


@pytest.mark.parametrize("nx,ny", VERTICAL_BRACKET_CELLS)
def test_bracket_solid_datums_and_actual_step_roundtrip(nx, ny, tmp_path):
    spec = Accessory("vertical-tile-bracket", nx=nx, ny=ny)
    part = make_accessory(spec)
    datums = accessory_datums(spec)
    assert part.is_valid and len(part.solids()) == 1
    assert tuple(part.bounding_box().min) == pytest.approx((0, 0, -12.8), abs=1e-5)
    assert tuple(part.bounding_box().max) == pytest.approx(
        (60 * nx, 60 * ny, 60 * ny + 7.578174593052), abs=1e-5
    )
    assert len(datums["mount_centers"]) == nx * ny
    assert len(datums["panel_plug_centers"]) == nx * ny
    assert datums["panel_seat_y"] == 60 * ny - 13
    assert datums["panel_plug_tip_y"] == pytest.approx(60 * ny - 0.2)
    assert datums["panel_bottom_z"] == datums["bearing_z"] == 6.1
    assert datums["nominal_bearing_gap"] == 0
    assert datums["outward_tile_face"] == "underside"
    path = tmp_path / f"bracket_{nx}x{ny}.step"
    assert export_step(part, path)
    restored = import_step(path)
    assert restored.is_valid and len(restored.solids()) == 1
    assert abs(restored.volume - part.volume) < 1e-5
    assert tuple(restored.bounding_box().size) == pytest.approx(tuple(part.bounding_box().size))


@pytest.mark.parametrize(
    "nx,ny,expected",
    [(1, 2, 554282.8862565482), (2, 1, 332047.0339637722), (2, 2, 1108565.7725130974)],
)
def test_bracket_volume_fixture_and_only_nonbearing_lip_is_rounded(nx, ny, expected):
    spec = Accessory("vertical-tile-bracket", nx=nx, ny=ny)
    core = _vertical_bracket(spec, round_lip=False)
    rounded = make_accessory(spec)
    assert rounded.volume == pytest.approx(expected, abs=1e-5)
    assert volume(rounded.cut(core)) < 1e-5
    change = core.cut(rounded)
    assert volume(change) > 0
    box = change.bounding_box()
    assert box.min.Y >= 60 * ny - 1 - 1e-5
    assert box.min.Z >= 5.1 - 1e-5
    assert box.max.Z <= 6.1 + 1e-5
    assert any(
        f.geom_type == GeomType.CYLINDER
        and BRepAdaptor_Surface(f.wrapped).Cylinder().Radius() == pytest.approx(1)
        and f.bounding_box().min.Y >= 60 * ny - 1 - 1e-5
        for f in rounded.faces()
    )


@pytest.mark.parametrize("nx,ny", [(2, 1), (2, 2)])
def test_approved_unrounded_core_metrics(nx, ny):
    part = _vertical_bracket(Accessory("vertical-tile-bracket", nx=nx, ny=ny), round_lip=False)
    expected = {1: 332072.7861841645, 2: 1108591.5247334896}
    assert part.volume == pytest.approx(expected[ny], abs=1e-5)


@pytest.mark.parametrize("nx,ny", VERTICAL_BRACKET_CELLS)
def test_original_lower_base_and_both_plug_sets_are_retained(nx, ny):
    spec = Accessory("vertical-tile-bracket", nx=nx, ny=ny)
    part = make_accessory(spec)
    base = _mounted_base(spec, root_radius=1)
    assert (
        difference(
            clipped(part, 0, 0, -13, nx * 60, ny * 60, 16.1),
            clipped(base, 0, 0, -13, nx * 60, ny * 60, 16.1),
        )
        < 1e-5
    )
    # The former decorative upper-rim void is completely filled.
    band = Solid.make_box(nx * 60, ny * 60, 1).moved(Location((0, 0, 3.1)))
    assert volume(band.cut(part)) < 1e-5
    for x, y, z in accessory_datums(spec)["mount_centers"]:
        plug = make_plug().rotate(Axis.X, 180).moved(Location((x, y, z)))
        assert volume(plug.cut(part)) < 1e-5
    for point in accessory_datums(spec)["panel_plug_centers"]:
        plug = make_plug().rotate(Axis.X, -90).moved(Location(point))
        assert volume(plug.cut(part)) < 1e-5


@pytest.mark.parametrize("nx,ny", VERTICAL_BRACKET_CELLS)
@pytest.mark.parametrize("holes", [False, True])
def test_separate_tile_insertion_bearing_and_solid_backing(nx, ny, holes):
    spec = Accessory("vertical-tile-bracket", nx=nx, ny=ny)
    part = make_accessory(spec)
    core = _vertical_bracket(spec, round_lip=False)
    tile_spec = Tile(
        nx, ny, hole_diameter=10 if holes else None, hole_scope="full" if holes else "interior"
    )
    tile = make_tile(tile_spec).rotate(Axis.X, 90).moved(Location((0, 60 * ny, 6.1)))
    assert tile.bounding_box().max.Y == pytest.approx(ny * 60, abs=1e-5)
    for offset in (0, 1, 4, 8, 12.8, 15):
        placed = tile.moved(Location((0, offset, 0)))
        assert abs(volume(part.intersect(placed)) - volume(core.intersect(placed))) < 1e-4
    bearing = sum(
        sum(f.area for f in q.faces()) if q else 0
        for top in contact_faces(part, 6.1, 1)
        for bottom in contact_faces(tile, 6.1, -1)
        for q in [top.intersect(bottom)]
    )
    if holes:
        assert bearing == pytest.approx(260.891859550497 * nx, abs=1e-5)
    assert bearing > 0
    assert part.is_inside(Vector(nx * 30, ny * 60 - 13 - 0.01, 20))
    # Exact unmodified neighbor tiles can extend sideways/upward with the same wall origin.
    for neighbor, x, z in (
        (Tile(1, ny), -60, 6.1),
        (Tile(1, ny), nx * 60, 6.1),
        (Tile(nx, 1), 0, 6.1 + ny * 60),
    ):
        shape = make_tile(neighbor).rotate(Axis.X, 90).moved(Location((x, ny * 60, z)))
        assert volume(part.intersect(shape)) < 1e-5


def test_bracket_variants_and_reference_only_interface_policy():
    variants = accessory_variants(BuildVolume(350, 320, 325))
    assert len(variants) == 41
    assert {(a.nx, a.ny) for a in variants if a.family == "vertical-tile-bracket"} == set(
        VERTICAL_BRACKET_CELLS
    )
    assert not any(a.family == "lock-90" for a in variants)
    custom = Interface(pitch=65)
    assert not any(
        a.family == "vertical-tile-bracket"
        for a in accessory_variants(BuildVolume(350, 320, 325), custom)
    )
    with pytest.raises(ValueError, match="requires 60 mm"):
        Accessory("vertical-tile-bracket", nx=2, interface=custom)
    with pytest.raises(ValueError, match="was replaced"):
        Accessory("lock-90")
    a = accessory_design(Accessory("vertical-tile-bracket", nx=1, ny=2))
    b = accessory_design(Accessory("vertical-tile-bracket", nx=2, ny=1))
    assert a.name != b.name
    assert a.apply_orientation_to_bambu and a.recommended_print_rotation_x == 135
    assert make_accessory(
        replace(
            Accessory("vertical-tile-bracket", nx=2), interface=Interface(joint_style="full-height")
        )
    ).is_valid
