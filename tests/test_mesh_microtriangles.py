"""Only CAD-supported kernel-scale triangular mesh cracks may be filled."""

import numpy as np
import pytest
from build123d import Solid

from cargo_grid import Tile, make_tile
from cargo_grid.meshes import _close_cad_microtriangles, _mesh_edges, checked_mesh


def test_exact_full_pattern_two_by_one_mesh_is_closed_without_moving_crack_vertices():
    shape = make_tile(Tile(2, 1, hole_diameter=10, hole_scope="full"))
    vertices, faces, report = checked_mesh(shape)
    counts, directions = _mesh_edges(faces)
    assert set(counts.values()) == {2} and not any(directions.values())
    assert report["closed_oriented_manifold"]
    assert report["seam_weld_mm"] <= 1e-5
    assert report["mesh_volume_mm3"] > 0
    for repair in report["cad_supported_microtriangle_repairs"]:
        assert not repair["vertices_moved"]
        assert repair["area_mm2"] <= 1e-7
        assert repair["maximum_edge_mm"] <= 0.1
        assert repair["max_sampled_cad_deviation_mm"] <= repair["cad_tolerance_mm"]
        assert repair["surface_sample_count"] == 15
    assert len(vertices) > 0


@pytest.mark.parametrize("scale", [1, 0.05])
def test_nonmicroscopic_triangular_holes_are_not_closed(scale):
    points = scale * np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    faces = np.array([[0, 1, 3], [1, 2, 3], [2, 0, 3]])
    counts, directions = _mesh_edges(faces)
    result, repairs = _close_cad_microtriangles(
        Solid.make_box(1, 1, 1), points, faces, counts, directions
    )
    assert np.array_equal(result, faces)
    assert repairs == []


def test_microscopic_crack_away_from_cad_is_rejected():
    points = np.array([[0.0, 0, 2], [0.04, 0, 2], [0.02, 1e-8, 2], [0.02, 0, 3]])
    faces = np.array([[0, 1, 3], [1, 2, 3], [2, 0, 3]])
    counts, directions = _mesh_edges(faces)
    result, repairs = _close_cad_microtriangles(
        Solid.make_box(1, 1, 1), points, faces, counts, directions
    )
    assert np.array_equal(result, faces)
    assert repairs == []
