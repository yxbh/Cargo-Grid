import pytest

from cargo_grid.catalogue import accessory_variants, tile_sizes
from cargo_grid.cli import main
from cargo_grid.parameters import BuildVolume


def test_complete_ordered_tile_family():
    assert set(tile_sizes(BuildVolume(246, 246, 13))) == {
        (x, y) for x in range(1, 5) for y in range(1, 5)
    }
    assert (5, 1) in tile_sizes(BuildVolume(306, 126, 13))
    assert (1, 5) in tile_sizes(BuildVolume(306, 126, 13))
    assert (5, 5) not in tile_sizes(BuildVolume(306, 126, 13))


def test_accessory_families_finite_and_complete():
    variants = accessory_variants(BuildVolume(246, 246, 120))
    assert len(variants) == 50
    assert {v.family for v in variants} == {
        "edge-x",
        "edge-y",
        "ramp",
        "corner-in",
        "corner-out",
        "support",
        "support-bit",
        "support-end",
        "vertical-tile-bracket",
        "vertical-stop",
        "lock-45",
        "plate",
    }


@pytest.mark.parametrize(
    "extra",
    [
        ["--holes"],
        ["--hole-diameter-mm", "10"],
        ["--stack-count", "2"],
        ["--bambu"],
        ["--material", "Unknown", "PETG", "#ffffff"],
    ],
)
def test_cli_rejects_incomplete_settings(tmp_path, extra):
    with pytest.raises(SystemExit) as caught:
        main(
            [
                "part",
                "--build-width-mm",
                "150",
                "--build-depth-mm",
                "150",
                "--build-height-mm",
                "50",
                "--output",
                str(tmp_path / "job"),
                *extra,
            ]
        )
    assert caught.value.code == 2
