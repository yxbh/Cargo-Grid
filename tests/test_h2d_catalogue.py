"""H2D-specific placement policy; generated projects remain unsliced and unverified physically."""

import json
from collections import Counter
from math import hypot

import pytest
from build123d import Box

import cargo_grid.catalogue as catalogue
import cargo_grid.cli as cli
from cargo_grid.accessories import Accessory, accessory_datums
from cargo_grid.catalogue import h2d_dual_safe_catalogue_job
from cargo_grid.cli import main
from cargo_grid.jobs import Design, Job
from cargo_grid.packing import PrintPlacement
from cargo_grid.parameters import BuildVolume


def test_h2d_dual_safe_plan_keeps_full_family_inventory_and_hardware_zones(monkeypatch):
    original_size = Design.bambu_size
    measured = Counter()

    def counted_size(design):
        measured[id(design)] += 1
        return original_size.fget(design)

    monkeypatch.setattr(Design, "bambu_size", property(counted_size))
    job = h2d_dual_safe_catalogue_job(hole_diameter=10, hole_scope="full")
    assert measured == Counter(id(design) for design in job.designs)
    families = Counter(design.parameters.get("family", "tile") for design in job.designs)
    assert families == {
        "tile": 25,
        "edge-x": 30,
        "edge-y": 30,
        "support": 5,
        "corner-in": 24,
        "corner-out": 36,
        "support-end": 4,
        "support-bit": 4,
        "vertical-tile-bracket": 5,
        "ramp": 10,
        "vertical-stop": 8,
        "lock-45": 2,
        "plate": 3,
    }
    assert len(job.designs) == len(job.print_placements) == 186
    plate_count = max(placement.plate for placement in job.print_placements) + 1
    assert set(job.plate_names) == set(range(plate_count))
    assert plate_count == 65
    assert job.part_gap == 10
    assert job.omitted == []
    assert job.placement_policy["common_reach_mm"] == {
        "min_x": 25,
        "max_x": 325,
        "min_y": 0,
        "max_y": 320,
        "max_z": 320,
    }
    exception_plate = job.print_placements[-1].plate
    assert job.plate_names[exception_plate] == "5x5 TILE - SINGLE NOZZLE ONLY - LEFT"
    assert any(
        name.startswith("Tile brackets - deep and shallow") for name in job.plate_names.values()
    )
    assert job.plate_settings[exception_plate] == {
        "filament_map_mode": "Manual",
        "filament_maps": "1",
        "filament_volume_maps": "0",
    }
    exception = job.designs[-1]
    assert "family" not in exception.parameters
    assert (exception.parameters["nx"], exception.parameters["ny"]) == (5, 5)
    assert exception.parameters["hole_diameter"] == 10
    assert exception.parameters["hole_scope"] == "full"
    by_plate = {}
    ramp_joins = set()
    ramp_plates = {}
    perimeter_plates = {}
    for design, placement in zip(job.designs, job.print_placements):
        family = design.parameters.get("family", "tile")
        if family == "ramp":
            join = design.parameters.get("ramp_join", "female")
            assert job.plate_names[placement.plate] == f"{join.title()} ramps"
            ramp_joins.add((design.parameters["nx"], join))
            ramp_plates.setdefault(placement.plate, []).append(
                (design.parameters["nx"], join, design.quantity)
            )
        elif family in {"edge-x", "edge-y", "corner-in", "corner-out"}:
            outward = design.parameters.get("edge_outward", 10.0)
            complete = design.parameters.get("complete_edge_holes", False)
            spec = Accessory(
                family,
                nx=design.parameters["nx"],
                variant=design.parameters["variant"],
                edge_outward=outward,
                complete_edge_holes=complete,
            )
            sexes = sorted(join["sex"] for join in accessory_datums(spec)["joins"])
            if family in {"edge-x", "edge-y"}:
                assert len(set(sexes)) == 1
                connector = sexes[0]
                kind = "edges"
            else:
                connector = (
                    sexes[0]
                    if len(sexes) == 1
                    else f"all-{sexes[0]}"
                    if sexes[0] == sexes[1]
                    else "male-female"
                )
                kind = "corners"
            mode = "complete holes" if complete else "plain"
            expected_name = f"{outward:g}mm {connector} {kind} - {mode}"
            assert job.plate_names[placement.plate] == expected_name
            perimeter_plates.setdefault(placement.plate, []).append(design.name)
        elif placement.plate != exception_plate:
            assert job.plate_names[placement.plate] not in {"Female ramps", "Male ramps"}
        width, depth, height = design.bambu_size
        if placement.rotation == 90:
            width, depth = depth, width
        bounds = (placement.x, placement.x + width, placement.y, placement.y + depth, height)
        by_plate.setdefault(placement.plate, []).append(bounds)
        if placement.plate == exception_plate:
            assert bounds[0] >= 5 - 1e-6 and bounds[1] <= 320 + 1e-6
            assert bounds[2] >= 5 - 1e-6 and bounds[3] <= 315 + 1e-6
        else:
            assert bounds[0] >= 30 - 1e-6 and bounds[1] <= 320 + 1e-6
            assert bounds[2] >= 5 - 1e-6 and bounds[3] <= 315 + 1e-6
            assert bounds[4] <= 320 + 1e-6
    assert ramp_joins == {(width, join) for width in range(1, 6) for join in ("female", "male")}
    assert ramp_plates == {
        12: [(width, "female", 1) for width in range(1, 6)],
        13: [(width, "male", 1) for width in range(1, 6)],
    }
    fixed_names = [
        "Normal stops 1",
        "Normal stops 2",
        "Tile brackets - deep and shallow 1",
        "Tile brackets - deep and shallow 2",
        "Angled stops",
        "Attachment plates",
    ]
    perimeter_names = [
        f"{outward:g}mm {connector} {kind} - {mode}"
        for outward in (10, 20, 30)
        for mode in ("plain", "complete holes")
        for kind, connectors in (
            ("edges", ("female", "male")),
            (
                "corners",
                ("female", "male", "all-female", "male-female", "all-male"),
            ),
        )
        for connector in connectors
    ]
    assert [job.plate_names[index] for index in range(14, 64)] == [
        *fixed_names,
        *perimeter_names,
        "Rails and connectors 1",
        "Rails and connectors 2",
    ]
    assert [job.plate_names[index] for index in sorted(perimeter_plates)] == perimeter_names
    assert len(perimeter_plates) == 42
    assert all(
        len(names) == (5 if " edges " in job.plate_names[plate] else 2)
        for plate, names in perimeter_plates.items()
    )
    assert job.plate_names[64] == "5x5 TILE - SINGLE NOZZLE ONLY - LEFT"
    assert len(by_plate[exception_plate]) == 1
    for rectangles in by_plate.values():
        for index, first in enumerate(rectangles):
            for second in rectangles[index + 1 :]:
                dx = max(0, first[0] - second[1], second[0] - first[1])
                dy = max(0, first[2] - second[3], second[2] - first[3])
                assert hypot(dx, dy) >= 10 - 1e-5
    assert all(
        design.bambu_object_settings["support_type"] == "normal(auto)"
        for design in job.designs
        if (
            design.parameters.get("family") == "ramp"
            and design.parameters.get("ramp_join", "female") == "female"
        )
        or design.parameters.get("family") == "vertical-stop"
        or (
            design.parameters.get("family") == "vertical-tile-bracket"
            and design.parameters.get("panel_height_cells") is not None
        )
    )
    assert all(
        not design.bambu_object_settings
        for design in job.designs
        if design.parameters.get("family") == "ramp"
        and design.parameters.get("ramp_join") == "male"
    )
    monkeypatch.setattr(
        catalogue,
        "h2d_dual_safe_catalogue_job",
        lambda **kwargs: job,
    )
    projects = catalogue.h2d_dual_safe_catalogue_projects(
        hole_diameter=10,
        hole_scope="full",
    )
    assert [len(project.plate_names) for project in projects] == [36, 29]
    assert [
        project.placement_policy["catalogue_set"]["global_visible_plate_range"]
        for project in projects
    ] == [[1, 36], [37, 65]]
    assert [
        project.placement_policy["catalogue_set"]["project_visible_plate_range"]
        for project in projects
    ] == [[1, 36], [1, 29]]
    assert [
        project.plate_names[index]
        for project in projects
        for index in range(len(project.plate_names))
    ] == [job.plate_names[index] for index in range(65)]
    assert [id(design) for project in projects for design in project.designs] == [
        id(design) for design in job.designs
    ]
    assert projects[0].plate_settings == {}
    assert projects[1].plate_settings == {
        28: {
            "filament_map_mode": "Manual",
            "filament_maps": "1",
            "filament_volume_maps": "0",
        }
    }
    assert "exception" not in projects[0].placement_policy
    assert projects[1].placement_policy["exception"]["global_visible_plate"] == 65
    assert projects[1].placement_policy["exception"]["project_visible_plate"] == 29
    assert projects[1].placement_policy["exception"]["plate"] == 29
    assert all(
        max(placement.plate for placement in project.print_placements) < 36 for project in projects
    )


@pytest.mark.parametrize(
    "extra,message",
    [
        ([], "requires --bambu"),
        (
            [
                "--bambu",
                "--material",
                "Bambu PETG Basic @BBL H2D 0.8 nozzle",
                "PETG",
                "#637b70",
                "--nozzle-diameter-mm",
                ".8",
                "--layer-height-mm",
                ".32",
                "--build-width-mm",
                "349",
            ],
            "unmodified H2D build envelope",
        ),
    ],
)
def test_h2d_dual_safe_cli_rejects_incomplete_hardware_requests(extra, message, tmp_path, capsys):
    command = [
        "catalogue",
        "--h2d-dual-safe",
        "--build-width-mm",
        "350",
        "--build-depth-mm",
        "320",
        "--build-height-mm",
        "325",
        "--output",
        str(tmp_path / "catalogue"),
    ]
    command.extend(extra)
    with pytest.raises(SystemExit) as error:
        main(command)
    assert error.value.code == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "catalogue").exists()


def test_h2d_dual_safe_cli_exports_two_standalone_projects(
    tmp_path,
    monkeypatch,
    capsys,
):
    build = BuildVolume(350, 320, 325)
    first = Job(
        [Design("first", Box(1, 1, 1), {})],
        build,
        "catalogue",
        print_placements=[PrintPlacement(35, 5, 5, 0)],
        plate_names={index: f"Global plate {index + 1}" for index in range(36)},
        placement_policy={
            "catalogue_set": {
                "project_number": 1,
                "project_count": 2,
                "global_visible_plate_range": [1, 36],
                "project_visible_plate_range": [1, 36],
            }
        },
    )
    second = Job(
        [Design("second", Box(1, 1, 1), {})],
        build,
        "catalogue",
        print_placements=[PrintPlacement(28, 5, 5, 0)],
        plate_names={index: f"Global plate {index + 37}" for index in range(29)},
        placement_policy={
            "catalogue_set": {
                "project_number": 2,
                "project_count": 2,
                "global_visible_plate_range": [37, 65],
                "project_visible_plate_range": [1, 29],
            }
        },
    )
    monkeypatch.setattr(
        cli,
        "h2d_dual_safe_catalogue_projects",
        lambda **kwargs: (first, second),
    )
    calls = []

    def fake_export(job, output, *, stl, bambu, stack=None):
        calls.append((job, output, stl, bambu, stack))
        output.mkdir(parents=True)
        (output / "job.3mf").write_bytes(b"project")
        manifest = output / "manifest.json"
        manifest.write_text("{}\n")
        return manifest

    monkeypatch.setattr(cli, "export_job", fake_export)
    output = tmp_path / "full-catalogue"
    command = [
        "catalogue",
        "--h2d-dual-safe",
        "--build-width-mm",
        "350",
        "--build-depth-mm",
        "320",
        "--build-height-mm",
        "325",
        "--bambu",
        "--material",
        "Bambu PETG Basic @BBL H2D 0.8 nozzle",
        "PETG",
        "#637b70",
        "--nozzle-diameter-mm",
        "0.8",
        "--layer-height-mm",
        "0.32",
        "--no-stl",
        "--output",
        str(output),
    ]
    assert main(command) == 0
    index = json.loads((output / "manifest.json").read_text())
    assert index["kind"] == "catalogue-set"
    assert index["design_count"] == 2
    assert index["plate_count"] == 65
    assert index["projects"] == [
        {
            "project_number": 1,
            "visible_plate_range": [1, 36],
            "plate_count": 36,
            "design_count": 1,
            "directory": "plates-01-to-36",
            "manifest": "plates-01-to-36/manifest.json",
            "bambu_project": "plates-01-to-36/job.3mf",
        },
        {
            "project_number": 2,
            "visible_plate_range": [37, 65],
            "plate_count": 29,
            "design_count": 1,
            "directory": "plates-37-to-65",
            "manifest": "plates-37-to-65/manifest.json",
            "bambu_project": "plates-37-to-65/job.3mf",
        },
    ]
    assert [call[1].name for call in calls] == ["plates-01-to-36", "plates-37-to-65"]
    assert all(not call[2] and call[3] is not None and call[4] is None for call in calls)
    assert capsys.readouterr().out.strip() == str(output / "manifest.json")
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(SystemExit) as error:
        main(command)
    assert error.value.code == 2
    assert len(calls) == 2
    assert (output / "manifest.json").read_bytes() == before
    assert "output directory is not empty" in capsys.readouterr().err
