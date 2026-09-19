"""H2D-specific placement policy; generated projects remain unsliced and unverified physically."""

from collections import Counter
from math import hypot

import pytest

from cargo_grid.accessories import Accessory, accessory_datums
from cargo_grid.catalogue import h2d_dual_safe_catalogue_job
from cargo_grid.cli import main
from cargo_grid.jobs import Design


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
    assert plate_count <= 36
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
    perimeter_sets = {}
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
            else:
                connector = (
                    sexes[0]
                    if len(sexes) == 1
                    else f"all-{sexes[0]}"
                    if sexes[0] == sexes[1]
                    else "male-female"
                )
            mode = "complete holes" if complete else "plain"
            expected_name = f"{outward:g}mm edges and corners - {mode}"
            actual_name = job.plate_names[placement.plate]
            assert actual_name == expected_name or (
                actual_name.startswith(f"{expected_name} ")
                and actual_name.removeprefix(f"{expected_name} ").isdigit()
            )
            perimeter_plates.setdefault(placement.plate, []).append(design.name)
            perimeter_set = perimeter_sets.setdefault(
                (outward, complete),
                {"plates": set(), "names": [], "connectors": set()},
            )
            perimeter_set["plates"].add(placement.plate)
            perimeter_set["names"].append(design.name)
            perimeter_set["connectors"].add(connector)
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
    ordered_names = [job.plate_names[index] for index in range(plate_count)]
    assert ordered_names[14:20] == fixed_names
    assert set(perimeter_sets) == {
        (outward, complete) for outward in (10, 20, 30) for complete in (False, True)
    }
    assert all(len(group["names"]) == 20 for group in perimeter_sets.values())
    assert all(
        group["connectors"] == {"female", "male", "all-female", "male-female", "all-male"}
        for group in perimeter_sets.values()
    )
    for (outward, complete), group in perimeter_sets.items():
        title = f"{outward:g}mm edges and corners - {'complete holes' if complete else 'plain'}"
        plates = sorted(group["plates"])
        expected_names = (
            [title]
            if len(plates) == 1
            else [f"{title} {index}" for index in range(1, len(plates) + 1)]
        )
        assert [job.plate_names[plate] for plate in plates] == expected_names
    perimeter_plate_order = [
        plate
        for key in sorted(perimeter_sets, key=lambda item: (item[0], item[1]))
        for plate in sorted(perimeter_sets[key]["plates"])
    ]
    assert perimeter_plate_order == sorted(perimeter_plates)
    assert ordered_names[perimeter_plate_order[-1] + 1 : exception_plate] == [
        "Rails and connectors 1",
        "Rails and connectors 2",
    ]
    assert job.placement_policy["perimeter_grouping"] == "outward width and boundary-hole mode"
    assert exception_plate == plate_count - 1
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
