#!/usr/bin/env python3
"""Deriva uma grade terrestre fixa de 1° do TopoJSON, sem ler eventos."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_arc(topology: dict, index: int, cache: dict[int, list]) -> list:
    original = index
    reverse = index < 0
    index = ~index if reverse else index
    if index not in cache:
        scale = topology["transform"]["scale"]
        translate = topology["transform"]["translate"]
        x = y = 0
        points = []
        for dx, dy in topology["arcs"][index]:
            x += dx; y += dy
            points.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        cache[index] = points
    points = cache[index]
    return list(reversed(points)) if reverse else points


def ring(topology: dict, indexes: list[int], cache: dict) -> list:
    output = []
    for index in indexes:
        points = decode_arc(topology, index, cache)
        output.extend(points if not output else points[1:])
    return output


def polygons(topology: dict) -> list:
    geometry = topology["objects"]["land"]["geometries"][0]
    raw = geometry["arcs"]
    if geometry["type"] == "Polygon":
        raw = [raw]
    cache = {}
    result = []
    for polygon in raw:
        rings = [ring(topology, indexes, cache) for indexes in polygon]
        xs = [point[0] for point in rings[0]]; ys = [point[1] for point in rings[0]]
        result.append((min(xs), min(ys), max(xs), max(ys), rings))
    return result


def inside_ring(x: float, y: float, points: list) -> bool:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def center_on_land(lon: float, lat: float, shapes: list) -> bool:
    for minx, miny, maxx, maxy, rings in shapes:
        if minx <= lon <= maxx and miny <= lat <= maxy and inside_ring(lon, lat, rings[0]):
            if not any(inside_ring(lon, lat, hole) for hole in rings[1:]):
                return True
    return False


def coastline_cells(shapes: list) -> set[tuple[int, int]]:
    """Rasteriza o contorno com margem de uma célula, sem usar eventos."""
    result = set()
    for _, _, _, _, rings in shapes:
        for points in rings:
            for a, b in zip(points, points[1:]):
                x0, y0 = a; x1, y1 = b
                dx = x1 - x0
                if dx > 180: dx -= 360
                elif dx < -180: dx += 360
                steps = max(1, math.ceil(max(abs(dx), abs(y1 - y0)) * 4))
                for step in range(steps + 1):
                    fraction = step / steps
                    x = ((x0 + dx * fraction + 180) % 360) - 180
                    y = y0 + (y1 - y0) * fraction
                    base = (math.floor(y), math.floor(x))
                    for dy in (-2, -1, 0, 1, 2):
                        for dx_cell in (-2, -1, 0, 1, 2):
                            lat = base[0] + dy
                            lon = ((base[1] + dx_cell + 180) % 360) - 180
                            if -90 <= lat < 90:
                                result.add((lat, lon))
    return result


def segment_intersects_box(a, b, minx, miny, maxx, maxy) -> bool:
    """Teste Liang–Barsky entre um segmento e a célula fechada."""
    x0, y0 = a; x1, y1 = b; dx, dy = x1 - x0, y1 - y0
    low, high = 0.0, 1.0
    for p, q in ((-dx, x0 - minx), (dx, maxx - x0), (-dy, y0 - miny), (dy, maxy - y0)):
        if p == 0:
            if q < 0: return False
            continue
        t = q / p
        if p < 0: low = max(low, t)
        else: high = min(high, t)
        if low > high: return False
    return True


def intersects_land_cell(lon: int, lat: int, shapes: list) -> bool:
    minx, miny, maxx, maxy = lon, lat, lon + 1, lat + 1
    samples = ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy), (lon + 0.5, lat + 0.5))
    for px0, py0, px1, py1, rings in shapes:
        if px1 < minx or px0 > maxx or py1 < miny or py0 > maxy:
            continue
        outer = rings[0]
        if any(inside_ring(x, y, outer) and not any(inside_ring(x, y, hole) for hole in rings[1:]) for x, y in samples):
            return True
        if any(minx <= x <= maxx and miny <= y <= maxy for x, y in outer):
            return True
        if any(segment_intersects_box(outer[i - 1], outer[i], minx, miny, maxx, maxy) for i in range(len(outer))):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data" / "catalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "grids" / "land-1deg.json")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    land = catalog["land"]  # deliberadamente não acessa catalog.events
    shapes = polygons(land)
    coastal = coastline_cells(shapes)
    cells = []
    for lat_floor in range(-90, 90):
        for lon_floor in range(-180, 180):
            if (lat_floor, lon_floor) in coastal or center_on_land(lon_floor + 0.5, lat_floor + 0.5, shapes):
                cells.append([lat_floor, lon_floor])
    output = {
        "schema_version": 1,
        "definition": "centro da célula de 1 grau em terra ou célula na margem conservadora de 2 graus do contorno world-atlas 110m",
        "independent_of_event_records": True,
        "source": {"file": str(args.catalog), "sha256": sha256(args.catalog), "json_pointer": "/land"},
        "cells": cells,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cells": len(cells)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
