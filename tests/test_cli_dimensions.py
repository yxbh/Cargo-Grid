"""Named printer dimensions are required, unambiguous and preserve geometry."""

import json
import re
from pathlib import Path

import pytest
from build123d import import_step

from cargo_grid.cli import main, parser

OPTIONS = ("--build-width-mm", "--build-depth-mm", "--build-height-mm")
COMPLETE = [OPTIONS[0], "150", OPTIONS[1], "150", OPTIONS[2], "50"]


@pytest.mark.parametrize("command", ["part", "layout", "catalogue"])
@pytest.mark.parametrize("supplied", [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2)])
def test_missing_build_axes_are_named_in_errors(command, supplied, tmp_path, capsys):
    args = [command, "--output", str(tmp_path / "job")]
    if command == "layout":
        args += ["--footprint", "120", "60"]
    for index in supplied:
        args += [OPTIONS[index], "150"]
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    message = capsys.readouterr().err.split("error:", 1)[1]
    assert "required" in message
    for index, option in enumerate(OPTIONS):
        assert (option in message) == (index not in supplied)
    assert not (tmp_path / "job").exists()


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "not-a-number"])
def test_build_values_report_axis_and_units(axis, value, tmp_path, capsys):
    args = list(COMPLETE)
    args[2 * axis + 1] = value
    with pytest.raises(SystemExit) as error:
        main(["part", *args, "--output", str(tmp_path / "job")])
    assert error.value.code == 2
    message = capsys.readouterr().err.split("error:", 1)[1]
    assert OPTIONS[axis] in message and "millimeters" in message and "greater than 0" in message
    assert not (tmp_path / "job").exists()


@pytest.mark.parametrize("other_dimensions", [[], COMPLETE])
def test_removed_ambiguous_option_is_not_an_abbreviation(tmp_path, capsys, other_dimensions):
    legacy = "--" + "build"
    with pytest.raises(SystemExit) as error:
        main(
            [
                "part",
                *other_dimensions,
                legacy,
                "150",
                "150",
                "50",
                "--output",
                str(tmp_path / "job"),
            ]
        )
    message = capsys.readouterr().err
    assert error.value.code == 2 and "unrecognized option" in message
    assert all(option in message for option in OPTIONS)
    assert not (tmp_path / "job").exists()


@pytest.mark.parametrize("command", ["part", "layout", "catalogue"])
def test_help_explains_dimensions_and_multivalue_order(command, capsys):
    with pytest.raises(SystemExit) as error:
        parser().parse_args([command, "--help"])
    assert error.value.code == 0
    text = capsys.readouterr().out
    normalized = " ".join(text.split())
    for option in OPTIONS:
        assert option in text
    for explanation in (
        "left-right",
        "front-back",
        "maximum print height",
        "no default",
        "X_MM Y_MM Z_MM",
        "WIDTH_MM DEPTH_MM",
    ):
        assert explanation in normalized
    assert not re.search(r"--build(?:[ =,]|$)", text)


def test_named_dimensions_generate_the_same_two_by_one_contract(tmp_path):
    output = tmp_path / "job"
    assert (
        main(
            [
                "part",
                *COMPLETE,
                "--cells",
                "2",
                "1",
                "--quantity",
                "2",
                "--no-stl",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    manifest = json.loads((output / "manifest.json").read_text())
    assert {key: manifest["build"][key] for key in ("x", "y", "z")} == {"x": 150, "y": 150, "z": 50}
    design = manifest["designs"][0]
    assert design["quantity"] == 2
    assert design["parameters"]["interface"]["joint_style"] == "original"
    assert design["parameters"]["hole_diameter"] is None
    shape = import_step(output / f"{design['name']}.step")
    assert shape.is_valid and len(shape.solids()) == 1 and shape.volume > 0
    assert tuple(shape.bounding_box().size) == pytest.approx((126, 66, 13), abs=1e-5)


def test_no_stale_build_triples_in_maintained_commands():
    root = Path(__file__).resolve().parents[1]
    files = [root / "README.md", root / "AGENTS.md", root / ".github/workflows/ci.yml"]
    files += list((root / "docs").glob("*.md")) + list((root / "examples").glob("*.py"))
    for path in files:
        assert not re.search(r"--build(?:[ =,`\"']|$)", path.read_text()), path
