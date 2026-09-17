"""Export contracts and optional real Bambu Studio interpretation checks."""

import json
import os
import posixpath
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import pytest
from build123d import Box, import_step

from cargo_grid.accessories import Accessory
from cargo_grid.catalogue import accessory_design
from cargo_grid.export import BambuSettings, Material, export_job, write_3mf
from cargo_grid.jobs import Design, Job, tile_design
from cargo_grid.packing import PrintPlacement
from cargo_grid.parameters import BuildVolume, Exclusion, Tile
from cargo_grid.stacking import StackSettings

CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PRODUCTION = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"


@pytest.fixture
def materials():
    return BambuSettings(
        (
            Material("Diagnostic PETG", "PETG", "#778877"),
            Material("Diagnostic PLA", "PLA", "#DDDDDD"),
        ),
        nozzle=0.4,
        layer_height=0.2,
    )


@pytest.fixture
def box_job():
    return Job(
        [Design("diagnostic_block", Box(20, 30, 2), {}, quantity=3)],
        BuildVolume(100, 80, 30, margin=5),
        "diagnostic",
    )


def _metadata(element):
    return {m.get("key"): m.get("value") for m in element.findall("metadata") if m.get("key")}


def _project_facts(path):
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        settings = json.loads(archive.read("Metadata/project_settings.config"))
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        models = {
            name: ET.fromstring(archive.read(name))
            for name in archive.namelist()
            if name.endswith(".model")
        }
        names = {}
        part_metadata = {}
        for obj in config.findall("object"):
            names[obj.get("id")] = _metadata(obj)["name"]
            for part in obj.findall("part"):
                part_metadata[obj.get("id"), part.get("id")] = (
                    _metadata(part).get("name", ""),
                    part.get("subtype"),
                    int(_metadata(part).get("extruder", _metadata(obj).get("extruder", "1"))),
                )
        plates = []
        for plate in config.findall("plate"):
            values = _metadata(plate)
            members = [
                (names[_metadata(instance)["object_id"]], int(_metadata(instance)["instance_id"]))
                for instance in plate.findall("model_instance")
            ]
            plates.append((int(values["plater_id"]), values["plater_name"], sorted(members)))

        def apply(point, value):
            if not value:
                return point
            numbers = [float(v) for v in value.split()]
            assert len(numbers) == 12
            return tuple(
                sum(point[j] * numbers[3 * j + i] for j in range(3)) + numbers[9 + i]
                for i in range(3)
            )

        def leaves(filename, ident, ancestors=()):
            key = filename, ident
            assert key not in ancestors, "cyclic component graph"
            root = models[filename]
            assert root.get("unit", "millimeter") == "millimeter"
            obj = root.find(f"./{{*}}resources/{{*}}object[@id='{ident}']")
            assert obj is not None
            vertices = obj.findall("./{*}mesh/{*}vertices/{*}vertex")
            if vertices:
                yield ident, [tuple(float(v.get(k)) for k in ("x", "y", "z")) for v in vertices]
            else:
                components = obj.findall("./{*}components/{*}component")
                assert components
                for component in components:
                    linked = component.get(f"{{{PRODUCTION}}}path")
                    target = filename
                    if linked:
                        target = (
                            linked.lstrip("/")
                            if linked.startswith("/")
                            else posixpath.normpath(
                                posixpath.join(posixpath.dirname(filename), linked)
                            )
                        )
                    for leaf_id, points in leaves(
                        target, component.get("objectid"), ancestors + (key,)
                    ):
                        yield leaf_id, [apply(p, component.get("transform")) for p in points]

        volumes = []
        for item in models["3D/3dmodel.model"].findall("./{*}build/{*}item"):
            ident = item.get("objectid")
            for leaf_id, points in leaves("3D/3dmodel.model", ident):
                coordinates = [apply(p, item.get("transform")) for p in points]
                bounds = tuple(
                    n
                    for axis in range(3)
                    for n in (min(p[axis] for p in coordinates), max(p[axis] for p in coordinates))
                )
                volumes.append((names[ident], *part_metadata[ident, leaf_id], bounds))
        return settings, sorted(plates), sorted(volumes)


def test_bracket_display_name_is_bambu_metadata_not_design_identity(materials, tmp_path):
    design = accessory_design(Accessory("vertical-tile-bracket", nx=2, ny=1))
    project = write_3mf(
        Job([design], BuildVolume(350, 320, 325), "part"),
        tmp_path / "bracket.3mf",
        bambu=materials,
    )
    _, plates, _ = _project_facts(tmp_path / "bracket.3mf")
    assert any(
        name.startswith("Wide tile bracket — 2 columns, 1 row (2x1)")
        for _, _, members in plates
        for name, _ in members
    )
    assert project["plates"][0]["items"][0]["design"] == design.name
    assert project["plates"][0]["items"][0]["display_name"] == design.display_name


def test_core_archive_has_valid_relationships_and_quantities(box_job, tmp_path):
    path = tmp_path / "core.3mf"
    result = write_3mf(box_job, path)
    assert result["format"] == "core-geometry"
    assert not result["application_import_verified"]
    assert not result["sliced"]
    with ZipFile(path) as archive:
        assert archive.testzip() is None
        assert "Metadata/project_settings.config" not in archive.namelist()
        relationships = ET.fromstring(archive.read("_rels/.rels"))
        target = next(iter(relationships)).get("Target").lstrip("/")
        root = ET.fromstring(archive.read(target))
        assert root.get("unit") == "millimeter"
        resources = root.findall("./{*}resources/{*}object")
        identifiers = {obj.get("id") for obj in resources}
        assert len(identifiers) == len(resources)
        assert len(root.findall("./{*}build/{*}item")) == 3
        for component in root.findall(".//{*}component"):
            assert component.get("objectid") in identifiers
        for mesh in root.findall(".//{*}mesh"):
            vertices = mesh.findall("./{*}vertices/{*}vertex")
            triangles = mesh.findall("./{*}triangles/{*}triangle")
            assert vertices and triangles
            for triangle in triangles:
                indices = [int(triangle.get(k)) for k in ("v1", "v2", "v3")]
                assert len(set(indices)) == 3
                assert all(0 <= i < len(vertices) for i in indices)


def test_bambu_explicit_materials_and_plate_membership(box_job, materials, tmp_path):
    path = tmp_path / "bambu.3mf"
    result = write_3mf(box_job, path, bambu=materials)
    settings, plates, volumes = _project_facts(path)
    assert settings["filament_type"] == ["PETG", "PLA"]
    assert settings["filament_colour"] == ["#778877", "#DDDDDD"]
    assert settings["filament_is_support"] == ["0", "0"]
    assert settings["printable_area"] == ["0x0", "100x0", "100x80", "0x80"]
    assert settings["printable_height"] == "30"
    assert settings["printer_settings_id"] and settings["print_settings_id"]
    assert sum(len(p[2]) for p in plates) == 3
    assert len({member for plate in plates for member in plate[2]}) == 3
    assert len(volumes) == 3
    assert all(v[2] == "normal_part" and v[3] == 1 for v in volumes)
    assert sum(p["quantity"] for p in result["plates"]) == 3
    assert settings["filament_map_mode"] == "Auto For Match"
    assert "filament_map" not in settings
    assert result["filament_assignment"] == {
        "mode": "Auto For Match",
        "physical_map_requested": None,
    }
    with ZipFile(path) as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        for plate in config.findall("plate"):
            values = _metadata(plate)
            assert values["filament_map_mode"] == "Auto For Match"
            assert "filament_maps" not in values and "filament_volume_maps" not in values


def test_actual_rotated_bounds_respect_margin_and_exclusion(materials, tmp_path):
    build = BuildVolume(100, 60, 20, margin=5, exclusions=(Exclusion(0, 0, 2, 2),))
    job = Job([Design("rotated_block", Box(40, 80, 2), {})], build, "diagnostic")
    path = tmp_path / "rotated.3mf"
    result = write_3mf(job, path, bambu=materials)
    _, _, volumes = _project_facts(path)
    assert result["plates"][0]["print_rotation"] == 90
    xmin, xmax, ymin, ymax, zmin, zmax = volumes[0][-1]
    assert xmin >= 5 - 1e-6 and ymin >= 5 - 1e-6
    assert xmax <= 95 + 1e-6 and ymax <= 55 + 1e-6
    assert zmin == pytest.approx(0)
    assert zmax == pytest.approx(2)


def test_explicit_placements_keep_plate_names_settings_and_reject_overlap(materials, tmp_path):
    designs = [
        Design("first", Box(20, 30, 2), {}),
        Design("second", Box(20, 30, 2), {}),
    ]
    job = Job(
        designs,
        BuildVolume(100, 100, 20),
        "catalogue",
        print_placements=[
            PrintPlacement(0, 5, 5, 0),
            PrintPlacement(0, 35, 5, 0),
        ],
        plate_names={0: "Related parts"},
        plate_settings={
            0: {
                "filament_map_mode": "Manual",
                "filament_maps": "1",
                "filament_volume_maps": "0",
            }
        },
    )
    result = write_3mf(job, tmp_path / "explicit.3mf", bambu=materials)
    assert result["packing"] == "explicit validated placements"
    assert result["plates"][0]["settings"]["filament_map_mode"] == "Manual"
    with ZipFile(tmp_path / "explicit.3mf") as archive:
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
    plate = _metadata(config.find("plate"))
    assert plate["plater_name"] == "Related parts"
    assert plate["filament_map_mode"] == "Manual"
    assert plate["filament_maps"] == "1"
    overlapping = Job(
        designs,
        BuildVolume(100, 100, 20),
        "catalogue",
        print_placements=[
            PrintPlacement(0, 5, 5, 0),
            PrintPlacement(0, 10, 10, 0),
        ],
    )
    with pytest.raises(ValueError, match="overlaps"):
        write_3mf(overlapping, tmp_path / "overlap.3mf", bambu=materials)


def test_job_exports_roundtripped_step_and_honest_manifest(box_job, tmp_path):
    directory = tmp_path / "new-job"
    manifest_path = export_job(box_job, directory)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["designs"][0]["quantity"] == 3
    assert manifest["designs"][0]["step_roundtrip"] == "passed"
    assert manifest["designs"][0]["step_precision_mode"] == "average"
    assert manifest["export"]["format"] == "core-geometry"
    assert not manifest["physical_fit_verified"]
    restored = import_step(directory / "diagnostic_block.step")
    assert restored.is_valid and len(restored.solids()) == 1
    assert tuple(restored.bounding_box().size) == pytest.approx((20, 30, 2))
    assert restored.volume == pytest.approx(1200)
    assert (directory / "diagnostic_block.stl").stat().st_size > 0
    before = manifest_path.read_bytes()
    with pytest.raises(ValueError, match="not empty"):
        export_job(box_job, directory)
    assert manifest_path.read_bytes() == before


def test_invalid_default_step_reimport_uses_strict_precision_fallback(tmp_path):
    design = tile_design(Tile(4, 3, hole_diameter=10, hole_scope="full"))
    manifest = json.loads(
        export_job(
            Job([design], BuildVolume(300, 250, 20), "part"),
            tmp_path / "full-hole",
            stl=False,
        ).read_text()
    )
    record = manifest["designs"][0]
    restored = import_step(tmp_path / "full-hole" / f"{design.name}.step")
    assert restored.is_valid and len(restored.solids()) == 1
    assert record["step_precision_mode"] in {"average", "least"}
    assert record["step_volume_delta_mm3"] <= record["step_volume_budget_mm3"]
    assert record["step_bounds_delta_mm"] <= 1e-5


@pytest.mark.parametrize(
    "name,kind,color",
    [
        ("", "PLA", "#FFFFFF"),
        ("PLA", "", "#FFFFFF"),
        ("PLA", "PLA", "FFFFFF"),
        ("PLA", "PLA", "#GGGGGG"),
    ],
)
def test_invalid_materials(name, kind, color):
    with pytest.raises(ValueError):
        Material(name, kind, color)


def test_stack_export_requires_backend_and_declared_slots(box_job, materials, tmp_path):
    settings = StackSettings(2, 1, 0.2, 1, 1, 2)
    with pytest.raises(ValueError, match="Bambu"):
        write_3mf(box_job, tmp_path / "invalid.3mf", stack=settings)
    with pytest.raises(ValueError, match="slot"):
        write_3mf(
            box_job,
            tmp_path / "invalid.3mf",
            bambu=materials,
            stack=StackSettings(2, 1, 0.2, 1, 1, 3),
        )
    assert not (tmp_path / "invalid.3mf").exists()


def test_stack_export_preserves_partial_batch_quantity(materials, tmp_path):
    design = tile_design(Tile())
    design.quantity = 3
    job = Job([design], BuildVolume(150, 150, 50), "diagnostic-stack")
    path = tmp_path / "stack.3mf"
    result = write_3mf(job, path, bambu=materials, stack=StackSettings(2, 1, 0.2, 1, 1, 2))
    assert [p["quantity"] for p in result["plates"]] == [2, 1]
    roles = Counter(v["role"] for p in result["plates"] for v in p["volumes"])
    assert roles["model"] == 3
    assert roles["support-base"] and roles["release-lower"] and roles["release-upper"]
    assert all(
        v["filament_slot"] == (2 if v["role"].startswith("release-") else 1)
        for p in result["plates"]
        for v in p["volumes"]
    )
    _, _, volumes = _project_facts(path)
    assert len(volumes) == sum(len(p["volumes"]) for p in result["plates"])
    assert max(v[-1][-1] for v in volumes) == pytest.approx(27, abs=1e-5)


@pytest.mark.parametrize("stacked", [False, True], ids=["multi-plate", "supported-stack"])
@pytest.mark.native
def test_real_bambu_import_export_preserves_project(box_job, materials, tmp_path, stacked):
    executable = os.environ.get("CARGO_GRID_BAMBU")
    if not executable:
        pytest.skip("Set CARGO_GRID_BAMBU to explicitly enable local Bambu Studio CLI checks")
    binary = Path(executable).resolve(strict=True)
    if stacked:
        design = tile_design(Tile())
        design.quantity = 3
        job = Job([design], BuildVolume(150, 150, 50), "diagnostic-stack")
    else:
        job = box_job
        job.designs[0].quantity = 23
    source = tmp_path / "input.3mf"
    destination = tmp_path / "roundtrip.3mf"
    write_3mf(
        job, source, bambu=materials, stack=StackSettings(2, 1, 0.2, 1, 1, 2) if stacked else None
    )
    before_settings, before_plates, before_volumes = _project_facts(source)
    with (tmp_path / "bambu.log").open("w") as log:
        result = subprocess.run(
            [
                str(binary),
                "--datadir",
                str(tmp_path / "settings"),
                "--debug",
                "2",
                "--arrange",
                "0",
                "--orient",
                "0",
                "--info",
                "--export-3mf",
                str(destination),
                str(source),
            ],
            cwd=tmp_path,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=180,
            check=False,
        )
    assert result.returncode == 0, (tmp_path / "bambu.log").read_text()
    after_settings, after_plates, after_volumes = _project_facts(destination)
    assert after_plates == before_plates
    assert len(after_volumes) == len(before_volumes)
    for key in (
        "printable_area",
        "printable_height",
        "filament_type",
        "filament_colour",
        "filament_is_support",
        "nozzle_diameter",
    ):
        assert after_settings[key] == before_settings[key]
    for before, after in zip(before_volumes, after_volumes):
        assert before[:-1] == after[:-1]
        assert after[-1] == pytest.approx(before[-1], abs=0.001)
