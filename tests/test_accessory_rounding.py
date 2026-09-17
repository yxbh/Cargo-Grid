"""Selective visible radii preserve real mating geometry, not only constants."""

from math import sqrt

import pytest
from build123d import Axis, GeomType, Location, Part, Solid, Vector, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Precision import Precision

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


@pytest.mark.parametrize("n,expected", [(1, 123711.10861061758), (2, 475485.9800915248)])
def test_filled_angled_stops_protect_connectors_and_round_free_edges(n, expected, tmp_path):
    spec = Accessory("lock-45", nx=n, ny=n)
    shape = make_accessory(spec)
    # Converge integration separately from the existing CAD construction-error contract.
    integrals = []
    for accuracy in (1e-10, 1e-12):
        properties = GProp_GProps()
        error = BRepGProp.VolumeProperties_s(shape.wrapped, properties, accuracy, True, False)
        assert error < 1e-10
        integrals.append(properties.Mass())
    assert abs(integrals[1] - integrals[0]) < 1e-7
    volume_budget = max(1e-6, shape.area * Precision.Confusion_s())
    assert integrals[1] == pytest.approx(expected, rel=0, abs=volume_budget), {
        "default_volume": shape.volume,
        "adaptive_volumes": integrals,
        "surface_area_mm2": shape.area,
        "existing_export_volume_budget_mm3": volume_budget,
    }
    base = _mounted_base(spec, root_radius=1, round_top=False)
    for x, y, _ in accessory_datums(spec)["mount_centers"]:
        region = Solid.make_box(48, 48, 13.2).moved(Location((x - 24, y - 24, -13)))
        expected_base = Part(base.intersect(region).solids())
        actual = Part(shape.intersect(region).solids())
        assert volume(expected_base.cut(actual)) + volume(actual.cut(expected_base)) < 1e-7
    assert shape.is_inside(Vector(n * 30, n * 30, 20))
    cargo_y = n * 60 - (10 - 4.1)
    assert shape.is_inside(Vector(n * 30, cargo_y - 3, 10))
    assert not shape.is_inside(Vector(n * 30, n * 60 - 5.8, 10))
    # The retained cargo envelope is6mm horizontally, hence6/sqrt(2) normal to its45deg plane.
    assert 6 / sqrt(2) == pytest.approx(4.242640687)
    path = tmp_path / "angled.step"
    assert export_step(shape, path)
    restored = import_step(path)
    assert restored.is_valid and len(restored.solids()) == 1
    assert any(
        face.geom_type == GeomType.CYLINDER
        and BRepAdaptor_Surface(face.wrapped).Cylinder().Radius() == pytest.approx(1)
        and face.bounding_box().max.Z > 49
        for face in restored.faces()
    )
