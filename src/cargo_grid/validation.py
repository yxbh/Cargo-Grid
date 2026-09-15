"""Optional local-reference measurements; no source geometry is stored or downloaded."""

from functools import lru_cache
from math import cos, radians, sin
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
from build123d import Part

from cargo_grid.interfaces import make_plug
from cargo_grid.parameters import Interface, Tile
from cargo_grid.tiles import make_tile

CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
PRODUCTION = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}"
IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"


def local_reference_mesh(path: Path, object_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Resolve IDs per model, component transforms, and production references."""
    with ZipFile(path) as archive:

        @lru_cache
        def objects(model_path: str) -> dict:
            root = ET.fromstring(archive.read(model_path))
            if root.get("unit", "millimeter") != "millimeter":
                raise ValueError("reference comparison requires millimeter units")
            return {o.get("id"): o for o in root.find(CORE + "resources")}

        def resolve(model_path: str, ident: str, ancestors: frozenset) -> tuple:
            key = (model_path, ident)
            if key in ancestors:
                raise ValueError("cyclic 3MF component graph")
            obj = objects(model_path)[ident]
            mesh = obj.find(CORE + "mesh")
            if mesh is not None:
                vertices = np.array(
                    [
                        [float(v.get(k)) for k in ("x", "y", "z")]
                        for v in mesh.find(CORE + "vertices")
                    ]
                )
                faces = np.array(
                    [
                        [int(v.get(k)) for k in ("v1", "v2", "v3")]
                        for v in mesh.find(CORE + "triangles")
                    ]
                )
                return vertices, faces
            vertices, faces, count = [], [], 0
            for c in obj.find(CORE + "components"):
                child = c.get(PRODUCTION + "path", model_path).lstrip("/")
                v, f = resolve(child, c.get("objectid"), ancestors | {key})
                transform = np.array([float(x) for x in c.get("transform", IDENTITY).split()])
                if transform.shape != (12,):
                    raise ValueError("invalid 3MF transform")
                vertices.append(v @ transform[:9].reshape((3, 3)) + transform[9:])
                faces.append(f + count)
                count += len(v)
            return np.concatenate(vertices), np.concatenate(faces)

        return resolve("3D/3dmodel.model", object_id, frozenset())


def shape_mesh(shape: Part) -> tuple[np.ndarray, np.ndarray]:
    vertices, triangles = shape.tessellate(0.002, 0.05)
    return np.array([tuple(v) for v in vertices]), np.array(triangles)


def segments(vertices: np.ndarray, triangles: np.ndarray, z: float) -> np.ndarray:
    p = vertices[triangles]
    active = (p[:, :, 2].min(axis=1) <= z) & (p[:, :, 2].max(axis=1) > z)
    p = p[active]
    result = []
    for tri in p:
        points = []
        for a, b in zip(tri, np.roll(tri, -1, axis=0)):
            if (a[2] <= z < b[2]) or (b[2] <= z < a[2]):
                points.append(a[:2] + (b[:2] - a[:2]) * ((z - a[2]) / (b[2] - a[2])))
        if len(points) == 2:
            result.append(points)
    return np.array(result)


def ray_radius(lines: np.ndarray, center: tuple[float, float], degrees: float) -> float:
    d = np.array([cos(radians(degrees)), sin(radians(degrees))])
    a = lines[:, 0] - center
    e = lines[:, 1] - lines[:, 0]
    determinant = d[0] * e[:, 1] - d[1] * e[:, 0]
    valid = abs(determinant) > 1e-12
    a, e, determinant = a[valid], e[valid], determinant[valid]
    t = (a[:, 0] * e[:, 1] - a[:, 1] * e[:, 0]) / determinant
    u = (a[:, 0] * d[1] - a[:, 1] * d[0]) / determinant
    hits = t[(t > 0) & (u >= -1e-8) & (u <= 1 + 1e-8)]
    if not len(hits):
        raise ValueError(f"missing section ray at {degrees} degrees")
    return float(hits.min())


def crossings(lines: np.ndarray, axis: int, coordinate: float) -> list[float]:
    if not len(lines):
        return []
    a, b = lines[:, 0], lines[:, 1]
    mask = ((a[:, axis] <= coordinate) & (coordinate < b[:, axis])) | (
        (b[:, axis] <= coordinate) & (coordinate < a[:, axis])
    )
    a, b = a[mask], b[mask]
    values = a[:, 1 - axis] + (coordinate - a[:, axis]) * (b[:, 1 - axis] - a[:, 1 - axis]) / (
        b[:, axis] - a[:, axis]
    )
    return sorted(float(x) for x in values)


def compare_reference(path: Path) -> dict:
    """Sample interfaces against original-original signed-clearance baselines."""
    original = local_reference_mesh(path, "44")
    original_plug = local_reference_mesh(path, "112")
    generated = shape_mesh(make_tile(Tile(interface=Interface(joint_style="original"))))
    generated_plug = shape_mesh(make_plug())
    rows = []
    # Source 3 mm blends have tessellation/section errors amplified near the
    # entry tangent. 0.008 mm covers measured chord error, not print tolerance.
    tolerance = 0.008
    for height in (2, 9.5, 10.5, 11, 12, 12.9):
        old = segments(*original, height - 6.5)
        new = segments(*generated, height)
        deviations = [
            (abs(ray_radius(old, (-3, -3), a) - ray_radius(new, (30, 30), a)), a)
            for a in range(0, 360, 2)
        ]
        error, angle = max(deviations)
        rows.append(
            {
                "feature": "socket",
                "height": height,
                "max_error_mm": error,
                "angle_degrees": angle,
                "pass": error <= tolerance,
            }
        )
    for height in (2, 9.5, 10, 10.5):
        old = segments(*original, height - 6.5)
        new = segments(*generated, height)
        for axis in (0, 1):
            for male in (True, False):
                deviations = []
                for depth in (0.1, 0.5, 1, 2, 3, 4, 5, 5.5, 5.9):
                    location = 60 + depth if male else depth
                    a = crossings(old, axis, location - 33)
                    b = crossings(new, axis, location)
                    if len(a) != len(b):
                        deviations.append((float("inf"), depth))
                    elif a:
                        deviations.append((max(abs(x + 33 - y) for x, y in zip(a, b)), depth))
                error, depth = max(deviations, default=(0.0, 0.0))
                rows.append(
                    {
                        "feature": f"{'male' if male else 'female'}-{'xy'[axis]}",
                        "height": height,
                        "depth": depth,
                        "max_error_mm": error if np.isfinite(error) else None,
                        "pass": error <= tolerance,
                    }
                )
    old_socket = segments(*original, 0)
    new_socket = segments(*generated, 6.5)
    old_plug = segments(*original_plug, 0)
    new_plug = segments(*generated_plug, 4.35)
    pairing = []
    for a in range(0, 360, 2):
        os = ray_radius(old_socket, (-3, -3), a)
        ns = ray_radius(new_socket, (30, 30), a)
        op = ray_radius(old_plug, (0, 0.08033), a)
        np_ = ray_radius(new_plug, (0, 0), a)
        pairing.append(
            {
                "angle": a,
                "original_original": os - op,
                "original_new": os - np_,
                "new_original": ns - op,
                "new_new": ns - np_,
            }
        )
    plug_error = max(abs(r["original_new"] - r["original_original"]) for r in pairing)
    rows.append(
        {
            "feature": "plug-throat-pairing",
            "max_error_mm": plug_error,
            "pass": plug_error <= tolerance,
        }
    )
    section_cache = {}

    def tile_section(new: bool, z: float):
        if any(abs(z - plane) < 1e-7 for plane in (0, 1, 9, 9.2, 10, 10.2, 11, 11.2, 12, 13)):
            z += 0.0001
        key = (new, round(z, 5))
        if key not in section_cache:
            section_cache[key] = segments(*(generated if new else original), z if new else z - 6.5)
        return section_cache[key]

    def edge_interval(new: bool, axis: int, z: float, depth: float, male: bool):
        if z < 0:
            return (-1e6, 1e6) if not male else None
        coordinate = (60 if male else 0) + depth
        offset = 0 if new else 33
        hits = [v + offset for v in crossings(tile_section(new, z), axis, coordinate - offset)]
        if male:
            if not hits:
                return None
            if len(hits) != 2:
                raise ValueError("unexpected male interface section topology")
            return tuple(hits)
        if len(hits) == 4:
            return hits[1], hits[2]
        if len(hits) == 2:
            return None
        if not hits:
            return (-1e6, 1e6)
        raise ValueError(
            f"unexpected female interface section topology: {new=}, {axis=}, "
            f"{z=}, {depth=}, {hits=}"
        )

    mating = []
    for axis in (0, 1):
        for lift in (0, 0.25, 0.5, 1, 2):
            for height in (1.5, 5, 8.5, 9.25, 9.5, 9.75, 10.1, 10.4, 10.7):
                for depth in (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 5.5, 5.9):
                    sample = {"axis": "xy"[axis], "lift": lift, "height": height, "depth": depth}
                    for male_new, female_new, name in (
                        (False, False, "original_original"),
                        (True, False, "new_original"),
                        (False, True, "original_new"),
                        (True, True, "new_new"),
                    ):
                        male = edge_interval(male_new, axis, height, depth, True)
                        female = edge_interval(female_new, axis, height - lift, depth, False)
                        if male is None:
                            sample[name] = None
                        elif female is None:
                            sample[name] = -(male[1] - male[0]) / 2
                        else:
                            sample[name] = min(male[0] - female[0], female[1] - male[1])
                    mating.append(sample)
    minimum = {
        name: min(r[name] for r in mating if r[name] is not None)
        for name in ("original_original", "new_original", "original_new", "new_new")
    }
    no_added_interference = all(
        minimum[name] >= minimum["original_original"] - tolerance
        for name in ("new_original", "original_new", "new_new")
    )

    def horizontal_planes(mesh):
        points = mesh[0][mesh[1]]
        flat = np.ptp(points[:, :, 2], axis=1) < 1e-7
        selected = points[flat]
        areas = (
            np.linalg.norm(
                np.cross(selected[:, 1] - selected[:, 0], selected[:, 2] - selected[:, 0]), axis=1
            )
            / 2
        )
        result = {}
        for z, area in zip(selected[:, 0, 2], areas):
            key = round(float(z), 5)
            result[key] = result.get(key, 0.0) + float(area)
        return sorted(z for z, area in result.items() if area > 50)

    source_planes = [z + 6.5 for z in horizontal_planes(original)]
    generated_planes = horizontal_planes(generated)
    plane_match = all(any(abs(a - b) <= tolerance for b in generated_planes) for a in source_planes)
    reference_plate_planes = horizontal_planes(original_plug)
    shoulder = sorted(reference_plate_planes)[-2]
    original_projection = float(original_plug[0][:, 2].max()) - shoulder
    new_projection = float(np.ptp(generated_plug[0][:, 2]))
    source_height = float(np.ptp(original[0][:, 2]))
    generated_height = float(np.ptp(generated[0][:, 2]))
    datum_pass = (
        plane_match
        and abs(original_projection - new_projection) <= tolerance
        and abs(source_height - generated_height) <= tolerance
    )
    # Lower straight flanks are the engagement surfaces; upper corner patches
    # are separately reported, never hidden behind a looser profile tolerance.
    engagement = [r for r in rows if r.get("height") == 2 or r["feature"] == "plug-throat-pairing"]
    functional_pass = no_added_interference and datum_pass and all(r["pass"] for r in engagement)
    surface_pass = all(row["pass"] for row in rows)
    return {
        "method": "local triangle-plane sections and 2-degree rays; not full-surface equivalence",
        "joint_style": "original",
        "scope": "Explicit original-style geometry only; does not validate full-height edge compatibility.",
        "tolerance_mm": tolerance,
        "reference_tessellation_note": "entry tangent amplification; no manufacturing allowance",
        "checked_pass": functional_pass,
        "functional_envelope_pass": functional_pass,
        "surface_profile_pass": surface_pass,
        "engagement_flanks_and_plug_pass": all(r["pass"] for r in engagement),
        "mating_datums": {
            "pass": datum_pass,
            "source_height_mm": source_height,
            "generated_height_mm": generated_height,
            "source_horizontal_planes_mm": source_planes,
            "generated_horizontal_planes_mm": generated_planes,
            "source_plug_projection_mm": original_projection,
            "generated_plug_projection_mm": new_projection,
            "source_mounted_bottom_clearance_mm": source_height - original_projection,
            "generated_mounted_bottom_clearance_mm": generated_height - new_projection,
            "mounting_frame": "shoulder at tile top; plug +Z reversed into socket",
        },
        "joining_mating_min_clearance_mm": minimum,
        "joining_mating_samples": mating,
        "mating_plane_nudge_mm": 0.0001,
        "rows": rows,
        "signed_radial_pairings": pairing,
        "not_checked": [
            "physical fit",
            "retention force",
            "full insertion path",
            "all accessory shoulders",
            "full-surface matching",
        ],
    }
