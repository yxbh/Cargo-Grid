import json
from dataclasses import replace
from math import cos, pi, sin

import pytest
from build123d import Location, Vector

from cargo_grid import BuildVolume, Interface, Tile, make_tile
from cargo_grid.accessories import Accessory, accessory_datums, make_accessory
from cargo_grid.catalogue import accessory_design, accessory_variants
from cargo_grid.cli import main
from cargo_grid.export import _checked_step_roundtrip
from cargo_grid.meshes import checked_mesh


def _assembly_contains(shapes, point):
    return any(shape.is_inside(point) for shape in shapes)


def _matching_tiles(spec):
    pitch = spec.interface.pitch
    placements = {}
    for join in accessory_datums(spec)["joins"]:
        x, y, _ = join["position"]
        if join["angle"] == 0:
            origin = (x - pitch / 2, y - pitch if join["sex"] == "female" else y, 0)
        elif join["angle"] == -90:
            origin = (x - pitch if join["sex"] == "female" else x, y - pitch / 2, 0)
        else:
            raise AssertionError(f"unsupported perimeter join angle: {join['angle']}")
        placements[origin] = make_tile(Tile(interface=spec.interface)).moved(Location(origin))
    return tuple(placements.values())


def _assert_completed_circle(shapes, center, height):
    for z in (1, height / 2, height - 1):
        for index in range(64):
            angle = 2 * pi * index / 64
            inside = Vector(
                center[0] + 4.99 * cos(angle),
                center[1] + 4.99 * sin(angle),
                z,
            )
            assert not _assembly_contains(shapes, inside)
        assert (
            sum(
                _assembly_contains(
                    shapes,
                    Vector(
                        center[0] + 5.01 * cos(2 * pi * index / 64),
                        center[1] + 5.01 * sin(2 * pi * index / 64),
                        z,
                    ),
                )
                for index in range(64)
            )
            >= 62
        )


@pytest.mark.parametrize("family", ["edge-x", "edge-y"])
@pytest.mark.parametrize("outward", [10, 20, 30])
@pytest.mark.parametrize("complete", [False, True])
def test_straight_edge_projection_and_hole_mode(family, outward, complete):
    spec = Accessory(
        family,
        nx=2,
        edge_outward=outward,
        complete_edge_holes=complete,
    )
    part = make_accessory(spec)
    expected_depth = outward + (spec.interface.male_join_depth if family == "edge-x" else 0)
    assert tuple(part.bounding_box().size) == pytest.approx((120, expected_depth, 13))
    datums = accessory_datums(spec)
    assert datums["edge_outward"] == outward
    assert datums["complete_edge_holes"] is complete
    assert datums["edge_hole_diameter"] == (10 if complete else None)
    assert datums["edge_hole_centers"] == (
        [(0, 0), (30, 0), (60, 0), (90, 0), (120, 0)] if complete else []
    )


@pytest.mark.parametrize("style", ["original", "full-height"])
@pytest.mark.parametrize("outward", [20, 30])
@pytest.mark.parametrize("complete", [False, True])
def test_wider_corner_variants_remain_single_valid_solids(style, outward, complete):
    interface = Interface(joint_style=style)
    specs = [
        *(
            Accessory(
                "corner-in",
                variant=v,
                interface=interface,
                edge_outward=outward,
                complete_edge_holes=complete,
            )
            for v in range(1, 5)
        ),
        *(
            Accessory(
                "corner-out",
                variant=v,
                interface=interface,
                edge_outward=outward,
                complete_edge_holes=complete,
            )
            for v in range(1, 7)
        ),
    ]
    for spec in specs:
        part = make_accessory(spec)
        assert part.is_valid and len(part.solids()) == 1
        assert part.volume > 0
        assert all(join["position"][0] in (0, 30, 60) for join in accessory_datums(spec)["joins"])


@pytest.mark.parametrize(
    "family,variants",
    [
        ("edge-x", range(1, 2)),
        ("edge-y", range(1, 2)),
        ("corner-in", range(1, 5)),
        ("corner-out", range(1, 7)),
    ],
)
@pytest.mark.parametrize("outward", [10, 20, 30])
def test_every_perimeter_join_completes_assembled_ten_mm_holes(family, variants, outward):
    for variant in variants:
        spec = Accessory(
            family,
            variant=variant,
            edge_outward=outward,
            complete_edge_holes=True,
        )
        shapes = (make_accessory(spec), *_matching_tiles(spec))
        for join in accessory_datums(spec)["joins"]:
            _assert_completed_circle(shapes, join["position"], spec.interface.height)


@pytest.mark.parametrize("outward", [10, 20, 30])
@pytest.mark.parametrize("variant,center", [(3, (60, 60)), (6, (0, 0))])
def test_completed_one_piece_outer_corner_makes_full_ten_mm_hole(outward, variant, center):
    tile = make_tile(Tile())
    corner = make_accessory(
        Accessory(
            "corner-out",
            variant=variant,
            edge_outward=outward,
            complete_edge_holes=True,
        )
    )
    shapes = (tile, corner)
    _assert_completed_circle(shapes, center, 13)


def test_completed_miter_terminations_cut_the_tile_corner_site():
    for variant in (1, 2, 4, 5):
        spec = Accessory("corner-out", variant=variant, complete_edge_holes=True)
        centers = accessory_datums(spec)["edge_hole_centers"]
        assert len(centers) == 3
        part = make_accessory(spec)
        for x, y in centers:
            for z in (1, 6.5, 12):
                assert not part.is_inside(Vector(x, y, z))


def test_custom_unit_completion_uses_only_tile_accepted_boundary_sites():
    interface = Interface(41)
    spec = Accessory(
        "edge-y",
        nx=2,
        interface=interface,
        edge_outward=30,
        complete_edge_holes=True,
    )
    assert accessory_datums(spec)["edge_hole_centers"] == [(0, 0), (41, 0), (82, 0)]
    part = make_accessory(spec)
    for x in (0, 41, 82):
        assert not part.is_inside(Vector(x, 4, 6.5))
    for x in (20.5, 61.5):
        assert part.is_inside(Vector(x, 4.5, 6.5))
    with pytest.raises(ValueError, match="no nominal 10 mm full-pattern boundary holes"):
        Accessory(
            "edge-y",
            interface=Interface(30),
            complete_edge_holes=True,
        )
    compact_catalogue = accessory_variants(
        BuildVolume(150, 150, 50),
        Interface(30),
    )
    assert any(spec.family == "edge-y" for spec in compact_catalogue)
    assert not any(
        spec.family in {"edge-x", "edge-y", "corner-in", "corner-out"} and spec.complete_edge_holes
        for spec in compact_catalogue
    )


def test_default_edge_and_corner_design_ids_are_stable():
    assert accessory_design(Accessory("edge-x")).name == ("edge-x_1x1_v1_original_ffbb300adc")
    assert accessory_design(Accessory("edge-y", nx=5)).name == ("edge-y_5x1_v1_original_dcd3b5c880")
    assert accessory_design(Accessory("corner-in", variant=4)).name == (
        "corner-in_1x1_v4_original_bbac2899f0"
    )
    assert accessory_design(Accessory("corner-out", variant=6)).name == (
        "corner-out_1x1_v6_original_349b8d994c"
    )


def test_nondefault_edge_name_parameters_step_and_mesh(tmp_path):
    spec = Accessory(
        "corner-out",
        variant=3,
        edge_outward=30,
        complete_edge_holes=True,
    )
    design = accessory_design(spec)
    assert "_out30mm_complete-holes_" in design.name
    assert design.parameters["edge_outward"] == 30
    assert design.parameters["complete_edge_holes"] is True
    assert len(design.holes) == 5
    restored, _, _, _, _ = _checked_step_roundtrip(design.shape, tmp_path / "edge.step")
    assert restored.is_valid and len(restored.solids()) == 1
    assert tuple(restored.bounding_box().size) == pytest.approx(
        tuple(design.shape.bounding_box().size), abs=1e-5
    )
    _, _, report = checked_mesh(design.shape)
    assert report["closed_oriented_manifold"]


def test_edge_cli_records_projection_completion_and_rejects_other_families(tmp_path, capsys):
    common = [
        "part",
        "--build-width-mm",
        "160",
        "--build-depth-mm",
        "160",
        "--build-height-mm",
        "30",
        "--no-stl",
    ]
    output = tmp_path / "edge"
    assert (
        main(
            [
                *common,
                "--family",
                "edge-y",
                "--edge-outward-mm",
                "20",
                "--complete-edge-holes",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    design = json.loads((output / "manifest.json").read_text())["designs"][0]
    assert design["parameters"]["edge_outward"] == 20
    assert design["parameters"]["complete_edge_holes"] is True
    assert design["compatibility"]["edge_outward_mm"] == 20
    assert design["compatibility"]["complete_edge_holes"] is True
    assert design["compatibility"]["edge_hole_diameter_mm"] == 10
    assert len(design["hole_placements"]) == 3

    with pytest.raises(SystemExit) as error:
        main(
            [
                *common,
                "--family",
                "plate",
                "--complete-edge-holes",
                "--output",
                str(tmp_path / "invalid"),
            ]
        )
    assert error.value.code == 2
    assert "--complete-edge-holes does not apply to plate" in capsys.readouterr().err


@pytest.mark.parametrize("unit,thickness", [(45, 8), (60, 18), (90, 13)])
def test_completed_wide_edge_keeps_hole_diameter_physical(unit, thickness):
    interface = Interface(unit, thickness)
    spec = Accessory(
        "edge-y",
        nx=2,
        interface=interface,
        edge_outward=30,
        complete_edge_holes=True,
    )
    part = make_accessory(spec)
    center = unit
    for z in (1, thickness / 2, thickness - 1):
        assert not part.is_inside(Vector(center, 4.99, z))
        assert part.is_inside(Vector(center, 5.01, z))
    assert accessory_datums(spec)["edge_hole_diameter"] == 10


def test_replacing_interface_preserves_edge_options():
    spec = Accessory("edge-y", edge_outward=20, complete_edge_holes=True)
    updated = replace(spec, interface=Interface(height=18))
    assert updated.edge_outward == 20
    assert updated.complete_edge_holes is True
