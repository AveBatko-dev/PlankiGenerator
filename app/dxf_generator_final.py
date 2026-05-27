from pathlib import Path
from typing import Any
import math

from config import CAD_STYLES
from app import dxf_generator_round as base
from app.dxf_generator import (
    Point,
    Segment,
    add_text,
    add_tick,
    fmt,
    get_angle_degrees,
    get_marker_segments,
    get_tick_segment,
    get_vector,
    normalize,
    offset_point,
    resolve_point,
    resolve_value,
)


def rotate_vector(vector: Point, angle_radians: float) -> Point:
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return vector[0] * cos_a - vector[1] * sin_a, vector[0] * sin_a + vector[1] * cos_a


def get_actual_hook_arc_points(geometry: dict[str, Any], steps: int = 24) -> list[Point]:
    start = geometry["p1"]
    end = geometry["p2"]
    bulge = float(geometry["bulge"])

    if bulge == 0:
        return [start, end]

    chord_length = base.get_distance(start, end)
    if chord_length == 0:
        return [start]

    center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    radius = chord_length / 2
    start_vector = normalize((start[0] - center[0], start[1] - center[1]))
    sign = 1 if bulge > 0 else -1

    points: list[Point] = []
    for step in range(max(1, steps) + 1):
        angle = sign * math.pi * step / max(1, steps)
        direction = rotate_vector(start_vector, angle)
        points.append((center[0] + direction[0] * radius, center[1] + direction[1] * radius))

    return points


def get_actual_hook_points(geometry: dict[str, Any]) -> list[Point]:
    points: list[Point] = [
        geometry["p0"],
        geometry["p1"],
        *get_actual_hook_arc_points(geometry=geometry, steps=int(geometry.get("arc_steps", 24))),
        geometry["p2"],
        geometry["p3"],
        geometry["inner_patch_start"],
        geometry["inner_patch_end"],
    ]
    return points


def get_hook_line_extension(geometry: dict[str, Any], line_direction: Point) -> float:
    base_point = geometry["base"]

    if geometry["position"] == "start":
        extend_direction = (-line_direction[0], -line_direction[1])
    elif geometry["position"] == "end":
        extend_direction = line_direction
    else:
        return 0.0

    max_projection = 0.0
    for point in get_actual_hook_points(geometry=geometry):
        projection = (point[0] - base_point[0]) * extend_direction[0] + (point[1] - base_point[1]) * extend_direction[1]
        max_projection = max(max_projection, projection)

    return max_projection + float(geometry["width"]) / 2


def get_dimension_normal(start: Point, end: Point, side: str) -> Point:
    line_direction = normalize(get_vector(start, end))

    if side == "left":
        return base.rotate_counterclockwise(line_direction)
    if side == "right":
        return base.rotate_clockwise(line_direction)

    raise ValueError(f"Unknown dimension side: {side}")


def get_dimension_hook_data(
    dim: dict,
    parameters: dict[str, float],
    normal: Point,
    line_direction: Point,
    template: dict,
    lines: dict[str, dict[str, Point]],
) -> tuple[float, float, float, float, float]:
    clearance_data = base.get_dimension_hook_clearance(
        dim=dim,
        parameters=parameters,
        normal=normal,
        template=template,
        lines=lines,
    )
    start_gap, end_gap, required_offset = clearance_data[:3]

    target_name = dim["target"]
    profile_width = base.get_profile_width(template=template)
    hook_line_clearance = resolve_value(dim.get("hook_line_clearance", max(4, profile_width * 2)), parameters)
    start_line_extend = 0.0
    end_line_extend = 0.0

    for hook in template.get("hooks", []):
        if hook.get("type") != "hook" or hook.get("attach_to") != target_name:
            continue

        geometry = base.get_single_hook_geometry(hook=hook, lines=lines, template=template)
        side_direction = geometry["side_direction"]

        if side_direction[0] * normal[0] + side_direction[1] * normal[1] < 0.5:
            continue

        line_extend = get_hook_line_extension(geometry=geometry, line_direction=line_direction) + hook_line_clearance

        if geometry["position"] == "start":
            start_line_extend = max(start_line_extend, line_extend)
        elif geometry["position"] == "end":
            end_line_extend = max(end_line_extend, line_extend)

    return start_gap, end_gap, required_offset, start_line_extend, end_line_extend


def get_parallel_dimension_geometry(
    dim: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    template: dict | None = None,
) -> dict[str, Any]:
    target_name = dim["target"]
    line = lines[target_name]
    p1 = line["start"]
    p2 = line["end"]
    offset = resolve_value(dim.get("offset", 22), parameters)
    side = dim.get("side", "left")
    normal = get_dimension_normal(start=p1, end=p2, side=side)
    line_direction = normalize(get_vector(p1, p2))

    profile_gap = base.get_profile_width(template=template) * 2 if template is not None else CAD_STYLES["profile"]["width"] * 2
    start_gap = profile_gap
    end_gap = profile_gap
    start_line_extend = 0.0
    end_line_extend = 0.0

    if template is not None:
        start_gap, end_gap, required_offset, start_line_extend, end_line_extend = get_dimension_hook_data(
            dim=dim,
            parameters=parameters,
            normal=normal,
            line_direction=line_direction,
            template=template,
            lines=lines,
        )
        offset = max(offset, required_offset)

    p1_dimension = (
        p1[0] - line_direction[0] * start_line_extend,
        p1[1] - line_direction[1] * start_line_extend,
    )
    p2_dimension = (
        p2[0] + line_direction[0] * end_line_extend,
        p2[1] + line_direction[1] * end_line_extend,
    )

    d1 = offset_point(p1_dimension, normal, offset)
    d2 = offset_point(p2_dimension, normal, offset)

    return {
        "p1": p1_dimension,
        "p2": p2_dimension,
        "normal": normal,
        "d1": d1,
        "d2": d2,
        "e1_start": offset_point(p1_dimension, normal, min(start_gap, offset)),
        "e1_end": d1,
        "e2_start": offset_point(p2_dimension, normal, min(end_gap, offset)),
        "e2_end": d2,
    }


def get_parallel_dimension_segments(
    dim: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    template: dict | None = None,
) -> list[Segment]:
    geometry = get_parallel_dimension_geometry(dim=dim, parameters=parameters, lines=lines, template=template)
    d1 = geometry["d1"]
    d2 = geometry["d2"]
    dimension_direction = get_vector(d1, d2)

    return [
        (d1, d2),
        (geometry["e1_start"], geometry["e1_end"]),
        (geometry["e2_start"], geometry["e2_end"]),
        get_tick_segment(d1, direction=dimension_direction, size=15),
        get_tick_segment(d2, direction=dimension_direction, size=15),
    ]


def draw_parallel_dimension(msp, dim: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]], template: dict | None = None):
    param_name = dim["param"]
    if param_name not in parameters:
        raise ValueError(f"Missing dimension parameter: {param_name}")

    target_name = dim["target"]
    if target_name not in lines:
        raise ValueError(f"Dimension target line not found: {target_name}")

    geometry = get_parallel_dimension_geometry(dim=dim, parameters=parameters, lines=lines, template=template)
    normal = geometry["normal"]
    d1 = geometry["d1"]
    d2 = geometry["d2"]

    attribs = {
        "layer": CAD_STYLES["dimensions"]["layer"],
        "color": CAD_STYLES["dimensions"]["color"],
        "lineweight": CAD_STYLES["dimensions"]["lineweight"],
    }

    msp.add_line(d1, d2, dxfattribs=attribs)
    msp.add_line(geometry["e1_start"], geometry["e1_end"], dxfattribs=attribs)
    msp.add_line(geometry["e2_start"], geometry["e2_end"], dxfattribs=attribs)

    dimension_direction = get_vector(d1, d2)
    add_tick(msp, d1, direction=dimension_direction, size=15)
    add_tick(msp, d2, direction=dimension_direction, size=15)

    mid = ((d1[0] + d2[0]) / 2, (d1[1] + d2[1]) / 2)
    text_position = offset_point(mid, normal, 12)

    if dim.get("text_rotation") == "auto":
        text_rotation = get_angle_degrees(d1, d2)
    else:
        text_rotation = dim.get("text_rotation", 0)

    add_text(
        msp=msp,
        text=fmt(parameters[param_name]),
        position=text_position,
        height=dim.get("text_height", CAD_STYLES["text"]["height"]),
        rotation=text_rotation,
    )


def draw_dimensions(msp, template: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    for dim in template.get("dimensions", []):
        dim_type = dim.get("type")

        if dim_type == "parallel_to_line":
            draw_parallel_dimension(msp=msp, dim=dim, parameters=parameters, lines=lines, template=template)
        else:
            raise ValueError(f"Unknown dimension type: {dim_type}")


def build_obstacle_lines(template: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]) -> list[Segment]:
    obstacles: list[Segment] = []

    for line in lines.values():
        obstacles.append((line["start"], line["end"]))

    for hook in template.get("hooks", []):
        hook_type = hook.get("type")

        if hook_type == "hook":
            geometry = base.get_single_hook_geometry(hook=hook, lines=lines, template=template)
            obstacles.extend(base.get_single_hook_segments(geometry=geometry))
        elif hook_type == "line":
            obstacles.append((resolve_point(hook["start"], parameters), resolve_point(hook["end"], parameters)))

    for dim in template.get("dimensions", []):
        if dim.get("type") == "parallel_to_line":
            obstacles.extend(get_parallel_dimension_segments(dim=dim, parameters=parameters, lines=lines, template=template))

    for marker in template.get("markers", []):
        marker_type = marker.get("type")
        if marker_type in ("triangle", "thickness_triangle"):
            obstacles.extend(get_marker_segments(marker=marker, parameters=parameters, lines=lines))

    for mark in template.get("angle_marks", []):
        if mark.get("enabled", False):
            obstacles.extend(base.get_angle_mark_segments(mark=mark, parameters=parameters, lines=lines))

    return obstacles


def generate_dxf(template: dict, output_path: Path, parameters: dict[str, float]) -> None:
    doc = base.setup_document()
    msp = doc.modelspace()
    lines = base.build_named_lines(template=template, parameters=parameters)
    obstacle_lines = build_obstacle_lines(template=template, parameters=parameters, lines=lines)

    base.draw_profile(msp=msp, template=template, lines=lines, parameters=parameters)
    base.draw_hooks(msp=msp, template=template, lines=lines, parameters=parameters, avoidance_lines=obstacle_lines)
    draw_dimensions(msp=msp, template=template, parameters=parameters, lines=lines)
    base.draw_markers(msp=msp, template=template, parameters=parameters, lines=lines)
    base.draw_angle_marks(msp=msp, template=template, parameters=parameters, lines=lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
