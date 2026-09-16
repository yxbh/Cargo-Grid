"""Selective visible radii preserve real mating geometry, not only constants."""

from math import sqrt

import pytest
from build123d import Axis, GeomType, Location, Part, Solid, Vector, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

from cargo_grid import Interface
from cargo_grid.accessories import (
    Accessory,
    _apply_joins,
    _edge_plan,
    _mounted_base,
    _support,
    accessory_datums,
    make_accessory,
)
from cargo_grid.interfaces import dovetail_face, full_height_part, horizontal_edges, prism


def volume(shape):
    return sum(s.volume for s in shape.solids()) if shape and shape.solids() else 0


def unrounded_edge(spec):
    face, joins = _edge_plan(spec)
    if spec.interface.joint_style == "original":
        part = _apply_joins(prism(face, spec.interface.height), joins, interface=spec.interface)
    else:
        male, female = [], []
        for join in joins:
            profile = dovetail_face(depth=join["depth"]).rotate(Axis.Z, join["angle"])
            profile = profile.moved(Location(join["position"]))
            (male if join["sex"] == "male" else female).append(profile)
        part = full_height_part(face, male, female, spec.interface.height, round_body_corners=False)
    return part.fillet(1, horizontal_edges(part, 0))


@pytest.mark.parametrize("style", ["original", "full-height"])
@pytest.mark.parametrize(
    "spec",
    [
        Accessory("edge-x", nx=2),
        Accessory("edge-y", nx=2),
        *(Accessory("corner-in", variant=v) for v in range(1, 5)),
        *(Accessory("corner-out", variant=v) for v in range(1, 7)),
    ],
)
def test_perimeter_r2_exists_in_step_and_join_region_is_unchanged(spec, style, tmp_path):
    from dataclasses import replace

    spec = replace(spec, interface=Interface(joint_style=style))
    before, after = unrounded_edge(spec), make_accessory(spec)
    assert after.volume < before.volume
    protected = Solid.make_box(500, 500, 10.2).moved(Location((-50, -50, 0)))
    assert volume(Part(before.intersect(protected).solids()).cut(after)) < 1e-5
    for join in accessory_datums(spec)["joins"]:
        region = Solid.make_box(52, join["depth"] + 5, 13).moved(Location((-26, -4, 0)))
        region = region.rotate(Axis.Z, join["angle"]).moved(Location(join["position"]))
        a, b = before.intersect(region), after.intersect(region)
        assert volume(Part(a.solids()).cut(Part(b.solids()))) < 1e-5
    path = tmp_path / "rounded.step"
    assert export_step(after, path)
    restored = import_step(path)
    assert restored.is_valid
    assert any(
        face.geom_type == GeomType.CYLINDER
        and BRepAdaptor_Surface(face.wrapped).Cylinder().Radius() == pytest.approx(2)
        for face in restored.faces()
    )


@pytest.mark.parametrize(
    "spec",
    [
        Accessory("support", nx=2),
        Accessory("support-bit", length=20),
        *(Accessory("support-end", variant=v) for v in range(1, 5)),
    ],
)
def test_support_r1_preserves_central_full_height_dovetails(spec, tmp_path):
    before, after = _support(spec, round_top=False), make_accessory(spec)
    assert after.volume < before.volume
    for join in accessory_datums(spec)["joins"]:
        region = Solid.make_box(36, join["depth"] + 5, 25).moved(Location((-18, -4, 0)))
        region = region.rotate(Axis.Z, join["angle"]).moved(Location(join["position"]))
        a, b = before.intersect(region), after.intersect(region)
        assert volume(Part(a.solids()).cut(Part(b.solids()))) < 1e-5
    below = Solid.make_box(60, 500, 24).moved(Location((-30, -10, -25)))
    assert volume(Part(before.intersect(below).solids()).cut(after)) < 1e-5
    path = tmp_path / "rail.step"
    assert export_step(after, path)
    restored = import_step(path)
    assert any(
        face.geom_type == GeomType.CYLINDER
        and BRepAdaptor_Surface(face.wrapped).Cylinder().Radius() == pytest.approx(1)
        and face.bounding_box().min.Z >= -1 - 1e-5
        for face in restored.faces()
    )


@pytest.mark.parametrize("n,expected", [(1, 64461.9715167621), (2, 196631.726183597)])
def test_full_depth_angled_webs_notch_removal_and_r1_cap(n, expected, tmp_path):
    spec = Accessory("lock-45", nx=n, ny=n)
    shape = make_accessory(spec)
    # Default non-adaptive quadrature is platform-sensitive on these curved faces.
    integrals = []
    for accuracy in (1e-10, 1e-12):
        properties = GProp_GProps()
        error = BRepGProp.VolumeProperties_s(shape.wrapped, properties, accuracy, True, False)
        assert error < 1e-10
        integrals.append(properties.Mass())
    assert abs(integrals[1] - integrals[0]) < 1e-7
    assert integrals[1] == pytest.approx(expected, abs=1e-5), {
        "default_volume": shape.volume,
        "adaptive_volumes": integrals,
    }
    base = _mounted_base(spec, root_radius=1)
    region = Solid.make_box(n * 60, n * 60, 16.1).moved(Location((0, 0, -13)))
    assert volume(Part(base.intersect(region).solids()).cut(shape)) < 1e-5
    assert volume(Part(shape.intersect(region).solids()).cut(base)) < 1e-5
    assert shape.is_inside(Vector(3, 60 * (n - 1) + 10, 47.5))
    assert shape.is_inside(Vector(n * 60 - 3, 60 * (n - 1) + 10, 47.5))
    assert shape.is_inside(Vector(5.99, n * 30, 20))
    assert not shape.is_inside(Vector(6.01, n * 30, 20))
    # The unaltered wall is6mm horizontally, hence6/sqrt(2) normal to its45deg plane.
    assert 6 / sqrt(2) == pytest.approx(4.242640687)
    path = tmp_path / "angled.step"
    assert export_step(shape, path)
    restored = import_step(path)
    assert restored.is_valid and len(restored.solids()) == 1
    assert any(
        face.geom_type == GeomType.CYLINDER
        and BRepAdaptor_Surface(face.wrapped).Cylinder().Radius() == pytest.approx(1)
        and face.bounding_box().max.Z > 49.9
        for face in restored.faces()
    )
