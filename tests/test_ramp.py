"""Approved ramp geometry and joins; print and physical performance remain unverified."""

import json
from dataclasses import replace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from build123d import GeomType, Location, Solid, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.Precision import Precision

from cargo_grid import BuildVolume, Interface, Tile, make_tile
from cargo_grid.accessories import (
    RAMP_CARRIER_RUN_MM,
    RAMP_FREE_EDGE_RADIUS_MM,
    RAMP_RUN_MM,
    Accessory,
    _ramp,
    accessory_datums,
    make_accessory,
)
from cargo_grid.catalogue import accessory_design, accessory_variants
from cargo_grid.cli import main
from cargo_grid.export import BambuSettings, Material, write_3mf
from cargo_grid.interfaces import tile_join_tool
from cargo_grid.jobs import Job
from cargo_grid.meshes import checked_mesh


def volume(shape) -> float:
    return sum(solid.volume for solid in shape.solids()) if shape else 0


@pytest.mark.parametrize("cells", range(1, 6))
def test_ramp_width_run_rise_rounding_step_and_mesh(cells, tmp_path):
    spec = Accessory("ramp", nx=cells)
    shape = make_accessory(spec)
    assert shape.is_valid and len(shape.solids()) == 1 and shape.volume > 0
    assert tuple(shape.bounding_box().min) == pytest.approx((0, 0, 0), abs=1e-5)
    assert tuple(shape.bounding_box().size) == pytest.approx(
        (60 * cells, RAMP_RUN_MM, 13), abs=1e-5
    )
    radii = [
        BRepAdaptor_Surface(face.wrapped).Cylinder().Radius()
        for face in shape.faces()
        if face.geom_type == GeomType.CYLINDER
    ]
    assert sum(radius == pytest.approx(RAMP_FREE_EDGE_RADIUS_MM) for radius in radii) == 8
    path = tmp_path / f"ramp-{cells}.step"
    assert export_step(shape, path)
    restored = import_step(path)
    budget = max(1e-6, shape.area * Precision.Confusion_s())
    assert restored.is_valid and len(restored.solids()) == 1
    assert abs(restored.volume - shape.volume) <= budget
    assert tuple(restored.bounding_box().size) == pytest.approx(tuple(shape.bounding_box().size))
    _, _, mesh = checked_mesh(shape)
    assert mesh["closed_oriented_manifold"] and mesh["mesh_volume_mm3"] > 0


@pytest.mark.parametrize("cells", range(1, 6))
def test_ramp_uses_exact_existing_female_join_and_mates_north_tile_edge(cells):
    interface = Interface()
    spec = Accessory("ramp", nx=cells, interface=interface)
    uncut = _ramp(spec, cut_joins=False)
    ramp = make_accessory(spec)
    cutters = [
        tile_join_tool(interface, depth=6.1, male=False).moved(Location(((cell + 0.5) * 60, 0, 0)))
        for cell in range(cells)
    ]
    expected = uncut.cut(*cutters).clean()
    assert volume(expected.cut(ramp)) + volume(ramp.cut(expected)) < 1e-7
    tile = make_tile(Tile(cells, 1, interface)).moved(Location((0, -60, 0)))
    assert volume(ramp.intersect(tile)) < 1e-7
    assert ramp.distance_to(tile) < 1e-7
    datums = accessory_datums(spec)
    assert datums["finished_run"] == 50
    assert datums["ramp_direction"] == "positive Y away from the tile"
    assert datums["mating_tile_edge"] == "north male edge at Y=0"
    assert [join["position"][0] for join in datums["joins"]] == [
        (cell + 0.5) * 60 for cell in range(cells)
    ]
    assert {join["sex"] for join in datums["joins"]} == {"female"}
    assert all(not join["open_through_top"] for join in datums["joins"])
    assert ramp.bounding_box().max.Z == pytest.approx(tile.bounding_box().max.Z)


def test_adjacent_ramps_meet_without_overlap_and_multi_cell_part_avoids_internal_seams():
    one = make_accessory(Accessory("ramp"))
    adjacent = one.moved(Location((60, 0, 0)))
    assert volume(one.intersect(adjacent)) < 1e-8
    assert one.distance_to(adjacent) < 1e-7
    two = make_accessory(Accessory("ramp", nx=2))
    assert two.is_valid and len(two.solids()) == 1
    plane = Solid.make_box(0.02, RAMP_RUN_MM, 13).moved(Location((59.99, 0, 0)))
    assert volume(two.intersect(plane)) > 0


def test_one_cell_production_shape_retains_approved_volume_fixture():
    production = make_accessory(Accessory("ramp"))
    budget = max(1e-6, production.area * Precision.Confusion_s())
    assert abs(production.volume - 25632.431011391003) <= budget


def test_catalogue_includes_every_ramp_width_that_fits_selected_envelope():
    variants = accessory_variants(BuildVolume(350, 320, 325))
    ramps = [spec for spec in variants if spec.family == "ramp"]
    assert len(variants) == 54
    assert [spec.nx for spec in ramps] == [1, 2, 3, 4, 5]
    assert all(spec.ny == 1 for spec in ramps)
    compact = [
        spec.nx for spec in accessory_variants(BuildVolume(246, 246, 120)) if spec.family == "ramp"
    ]
    assert compact == [1, 2, 3, 4]
    assert not any(
        spec.family == "ramp"
        for spec in accessory_variants(
            BuildVolume(350, 320, 325),
            Interface(joint_style="full-height"),
        )
    )


def test_cli_and_api_use_plain_width_cells_and_fixed_run(tmp_path):
    output = tmp_path / "ramp"
    assert (
        main(
            [
                "part",
                "--family",
                "ramp",
                "--width-cells",
                "3",
                "--build-width-mm",
                "350",
                "--build-depth-mm",
                "320",
                "--build-height-mm",
                "325",
                "--no-stl",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    manifest = json.loads((output / "manifest.json").read_text())
    design = manifest["designs"][0]
    assert design["parameters"]["family"] == "ramp"
    assert (design["parameters"]["nx"], design["parameters"]["ny"]) == (3, 1)
    assert design["size_mm"] == pytest.approx([180, 50, 13])
    assert design["compatibility"]["tile_edge_interface_present"]
    assert not design["compatibility"]["x_attachment_interface_present"]
    assert "ramp_3x1" in accessory_design(Accessory("ramp", nx=3)).name


def test_bambu_ramp_scopes_normal_auto_without_changing_orientation_or_other_objects(tmp_path):
    ramp = accessory_design(Accessory("ramp", nx=3))
    plate = accessory_design(Accessory("plate"))
    assert not ramp.apply_orientation_to_bambu
    assert ramp.bambu_size == ramp.size
    assert ramp.bambu_object_settings == {
        "enable_support": "1",
        "support_type": "normal(auto)",
    }
    settings = BambuSettings((Material("PETG", "PETG", "#637b70"),), 0.4, 0.2)
    path = tmp_path / "mixed.3mf"
    report = write_3mf(
        Job([ramp, plate], BuildVolume(350, 320, 325), "catalogue"),
        path,
        bambu=settings,
    )
    items = [item for plate_record in report["plates"] for item in plate_record["items"]]
    ramp_item = next(item for item in items if item["design"] == ramp.name)
    plate_item = next(item for item in items if item["design"] == plate.name)
    assert ramp_item["object_settings"] == ramp.bambu_object_settings
    assert "source_to_project_transform" not in ramp_item
    assert "object_settings" not in plate_item
    with ZipFile(path) as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        project = json.loads(archive.read("Metadata/project_settings.config"))
    by_name = {}
    for obj in config.findall("object"):
        values = {entry.get("key"): entry.get("value") for entry in obj.findall("metadata")}
        by_name[values["name"]] = values
    assert by_name[f"{ramp.name}_batch_1"]["enable_support"] == "1"
    assert by_name[f"{ramp.name}_batch_1"]["support_type"] == "normal(auto)"
    assert "enable_support" not in by_name[f"{plate.name}_batch_2"]
    assert "enable_support" not in project
    with pytest.raises(ValueError, match="object settings"):
        write_3mf(
            Job(
                [replace(ramp, bambu_object_settings={})],
                BuildVolume(350, 320, 325),
                "part",
            ),
            tmp_path / "missing-object-settings.3mf",
            bambu=settings,
        )


def test_ramp_rejects_irrelevant_height_and_unsupported_interfaces():
    with pytest.raises(ValueError, match="original roofed joints"):
        Accessory("ramp", interface=Interface(pitch=65))
    with pytest.raises(ValueError, match="original roofed joints"):
        Accessory("ramp", interface=Interface(joint_style="full-height"))
    with pytest.raises(ValueError, match="height does not apply"):
        Accessory("ramp", height=120)
    with pytest.raises(ValueError, match="ramp uses nx"):
        Accessory("ramp", ny=2)


def test_approved_shape_constants_are_explicit():
    assert RAMP_RUN_MM == 50
    assert RAMP_CARRIER_RUN_MM == 10
    assert RAMP_FREE_EDGE_RADIUS_MM == 2
