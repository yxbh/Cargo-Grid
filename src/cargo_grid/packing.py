"""Deterministic first-fit rectangle packing, not an optimal nesting solver."""

from dataclasses import dataclass

from cargo_grid.parameters import BuildVolume, positive


@dataclass(frozen=True)
class PrintPlacement:
    plate: int
    x: float
    y: float
    rotation: int


def pack_sizes(
    sizes: list[tuple[float, float, float]],
    build: BuildVolume,
    *,
    gap: float = 2,
    pack: bool = True,
) -> list[PrintPlacement]:
    positive("part gap", gap, zero=True)
    occupied: list[list[tuple[float, float, float, float]]] = []
    results: dict[int, PrintPlacement] = {}
    order = (
        sorted(range(len(sizes)), key=lambda i: (-sizes[i][0] * sizes[i][1], i))
        if pack
        else range(len(sizes))
    )
    for index in order:
        size = sizes[index]
        for dimension in size:
            positive("part dimension", dimension)
        if build.placement(size) is None:
            raise ValueError(f"part {index} bounds {size} do not fit the usable envelope")
        chosen = None
        candidates = range(len(occupied) + 1) if pack else (len(occupied),)
        for plate in candidates:
            rectangles = occupied[plate] if plate < len(occupied) else []
            xs = {
                build.margin,
                *(x + w + gap for x, y, w, d in rectangles),
                *(a.x + a.width for a in build.exclusions),
            }
            ys = {
                build.margin,
                *(y + d + gap for x, y, w, d in rectangles),
                *(a.y + a.depth for a in build.exclusions),
            }
            for angle in (0, 90):
                w, d = size[:2] if angle == 0 else size[1::-1]
                for y in sorted(ys):
                    for x in sorted(xs):
                        if x < build.margin or y < build.margin:
                            continue
                        if x + w > build.x - build.margin - build.reserve_x + 1e-6:
                            continue
                        if y + d > build.y - build.margin - build.reserve_y + 1e-6:
                            continue
                        if any(
                            x < a.x + a.width and x + w > a.x and y < a.y + a.depth and y + d > a.y
                            for a in build.exclusions
                        ):
                            continue
                        if any(
                            x < rx + rw + gap - 1e-6
                            and x + w + gap > rx + 1e-6
                            and y < ry + rd + gap - 1e-6
                            and y + d + gap > ry + 1e-6
                            for rx, ry, rw, rd in rectangles
                        ):
                            continue
                        chosen = PrintPlacement(plate, x, y, angle)
                        if plate == len(occupied):
                            occupied.append([])
                        occupied[plate].append((x, y, w, d))
                        break
                    if chosen:
                        break
                if chosen:
                    break
            if chosen:
                break
        if chosen is None:
            raise ValueError(
                f"could not pack part {index}; exclusions or reservations block placement"
            )
        results[index] = chosen
    return [results[i] for i in range(len(sizes))]
