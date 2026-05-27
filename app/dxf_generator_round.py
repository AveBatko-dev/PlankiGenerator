from pathlib import Path
from typing import Any
import math

from config import CAD_STYLES
from app.dxf_generator import (
    Point,
    Segment,
    add_profile_line_label,
    add_profile_path,
    add_text,
    add_tick,
    build_named_lines,
    build_profile_path,
    draw_angle_marks,
    draw_markers,
    estimate_text_size,
    fmt,
    get_angle_degrees,
    get_angle_mark_segments,
    get_distance,
    get_marker_segments,
    get_template_default,
    get_tick_segment,
    get_vector,
    normalize,
    offset_point,
    resolve_point,
    resolve_value,
    rotate_clockwise,
    rotate_counterclockwise,
    setup_document,
)


PROFILE_WIDTH_SCALE = 2 / 3
ROUND_DISC_SEGMENTS = 32


def get_profile_width(template: dict) -> float:
    return get_template_default(
        template=template,
        name="profile_width",
        fallback=CAD_STYLES["profile"]["width"],
    ) * PROFILE_WIDTH_SCALE


def add_filled_disc(msp, center: Point, radius: float, segments: int = ROUND_DISC_SEGMENTS):
    if radius <= 0:
        return

    points = []
    for index in range(max(8, segments)):
        angle = 2 * math.pi * index / max(8, segments)
        points.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))

    hatch = msp.add_hatch(
        color=CAD_STYLES["profile"]["color"],
        dxfattribs={"layer": CAD_STYLES["profile"]["layer"]},
    )
    hatch.paths.add_polyline_path(points, is_closed=True)


def add_rounded_profile_path(msp, points: list[tuple[float, float, float]], width: float):
    add_profile_path(msp=msp, points=points, width=width)

    radius = width / 2
    seen: set[tuple[int, int]] = set()
    for point in points:
        center = (point[0], point[1])
        key = (round(center[0] * 1000), round(center[1] * 1000))
        if key in seen:
            continue
        seen.add(key)
        add_filled_disc(msp=msp, center=center, radius=radius)


def draw_profile(msp, template: dict, lines: dict[str, dict[str, Point]], parameters: dict[str, float]):
    profile_width = get_profile_width(template=template)

    points = build_profile_path(lines, template)
    add_rounded_profile_path(msp=msp, points=points, width=profile_width)

    for element in template["profile"]["elements"]:
        line = lines[element["name"]]
        add_profile_line_label(msp=msp, element=element, start=line["start"], end=line["end"], parameters=parameters)


def rotate_vector(vector: Point, angle_radians: float) -> Point:
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return vector[0] * cos_a - vector[1] * sin_a, vector[0] * sin_a + vector[1] * cos_a


def get_semicircle_segments(start: Point, end: Point, arc_side_direction: Point, steps: int = 16) -> list[Segment]:
    chord_length = get_distance(start, end)
    if chord_length == 0:
        return []

    center = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    radius = chord_length / 2
    start_vector = normalize((start[0] - center[0], start[1] - center[1]))
    side_direction = normalize(arc_side_direction)

    positive_mid = rotate_vector(start_vector, math.pi / 2)
    negative_mid = rotate_vector(start_vector, -math.pi / 2)
    positive_score = positive_mid[0] * side_direction[0] + positive_mid[1] * side_direction[1]
    negative_score = negative_mid[0] * side_direction[0] + negative_mid[1] * side_direction[1]
    sign = 1 if positive_score >= negative_score else -1

    points: list[Point] = []
    for step in range(max(1, steps) + 1):
        angle = sign * math.pi * step / max(1, steps)
        direction = rotate_vector(start_vector, angle)
        points.append((center[0] + direction[0] * radius, center[1] + direction[1] * radius))

    return list(zip(points[:-1], points[1:]))


def get_single_hook_geometry(hook: dict, lines: dict[str, dict[str, Point]], template: dict) -> dict[str, Any]:
    attach_to = hook["attach_to"]
    position = hook["position"]

    if attach_to not in lines:
        raise ValueError(f"Hook target line not found: {attach_to}")

    line = lines[attach_to]
    line_start = line["start"]
    line_end = line["end"]
    width = get_profile_width(template=template)
    length = float(hook["length"])
    angle = float(hook.get("angle", 90))

    if angle != 90:
        raise ValueError("Only 90 degree hooks are supported for now")

    line_direction = normalize(get_vector(line_start, line_end))
    hook_gap = float(hook.get("gap", length))
    tail_length = float(hook.get("tail_length", length))
    join_overlap = width * 1.6
    inner_join_overlap = width * 0.28
    arc_steps = int(hook.get("arc_obstacle_steps", 16))

    if position == "start":
        base = line_start
        side = hook.get("side", "right")

        if side == "right":
            side_direction = rotate_clockwise(line_direction)
            bulge = 1
        elif side == "left":
            side_direction = rotate_counterclockwise(line_direction)
            bulge = -1
        else:
            raise ValueError(f"Unknown hook side: {side}")

        p0 = (base[0] + line_direction[0] * join_overlap, base[1] + line_direction[1] * join_overlap)
        p1 = base
        p2 = (base[0] + side_direction[0] * hook_gap, base[1] + side_direction[1] * hook_gap)
        p3 = (p2[0] + line_direction[0] * tail_length, p2[1] + line_direction[1] * tail_length)
        inner_patch_start = (p2[0] - line_direction[0] * inner_join_overlap, p2[1] - line_direction[1] * inner_join_overlap)
        arc_side_direction = line_direction

    elif position == "end":
        base = line_end
        side = hook.get("side", "right")

        if side == "right":
            side_direction = rotate_clockwise(line_direction)
            bulge = -1
        elif side == "left":
            side_direction = rotate_counterclockwise(line_direction)
            bulge = 1
        else:
            raise ValueError(f"Unknown hook side: {side}")

        back_direction = (-line_direction[0], -line_direction[1])
        p0 = (base[0] + back_direction[0] * join_overlap, base[1] + back_direction[1] * join_overlap)
        p1 = base
        p2 = (base[0] + side_direction[0] * hook_gap, base[1] + side_direction[1] * hook_gap)
        p3 = (p2[0] + back_direction[0] * tail_length, p2[1] + back_direction[1] * tail_length)
        inner_patch_start = (p2[0] - back_direction[0] * inner_join_overlap, p2[1] - back_direction[1] * inner_join_overlap)
        arc_side_direction = back_direction

    else:
        raise ValueError(f"Unknown hook position: {position}")

    return {
        "width": width,
        "base": base,
        "p0": p0,
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "inner_patch_start": inner_patch_start,
        "inner_patch_end": p3,
        "line_direction": line_direction,
        "side_direction": side_direction,
        "arc_side_direction": arc_side_direction,
        "arc_steps": arc_steps,
        "bulge": bulge,
        "position": position,
    }


def get_single_hook_segments(geometry: dict[str, Any]) -> list[Segment]:
    arc_segments = get_semicircle_segments(
        start=geometry["p1"],
        end=geometry["p2"],
        arc_side_direction=geometry["arc_side_direction"],
        steps=geometry["arc_steps"],
    )

    return [
        (geometry["p0"], geometry["p1"]),
        *arc_segments,
        (geometry["p2"], geometry["p3"]),
        (geometry["inner_patch_start"], geometry["inner_patch_end"]),
    ]


def get_hook_points(geometry: dict[str, Any]) -> list[Point]:
    points: list[Point] = [geometry["p0"], geometry["p1"], geometry["p2"], geometry["p3"], geometry["inner_patch_start"], geometry["inner_patch_end"]]

    for start, end in get_single_hook_segments(geometry=geometry):
        points.extend([start, end])

    return points


def get_hook_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    points = get_hook_points(geometry=geometry)
    half_width = float(geometry["width"]) / 2
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs) - half_width, min(ys) - half_width, max(xs) + half_width, max(ys) + half_width


def get_dimension_normal_for_hook(hook: dict, template: dict, lines: dict[str, dict[str, Point]]) -> Point | None:
    attach_to = hook.get("attach_to")
    if not attach_to or attach_to not in lines:
        return None

    for dim in template.get("dimensions", []):
        if dim.get("type") != "parallel_to_line" or dim.get("target") != attach_to:
            continue

        line = lines[attach_to]
        line_direction = normalize(get_vector(line["start"], line["end"]))
        side = dim.get("side", "left")

        if side == "left":
            return rotate_counterclockwise(line_direction)
        if side == "right":
            return rotate_clockwise(line_direction)

        raise ValueError(f"Unknown dimension side: {side}")

    return None


def get_label_side_opposite_dimension(hook: dict, template: dict, lines: dict[str, dict[str, Point]]) -> str | None:
    dimension_normal = get_dimension_normal_for_hook(hook=hook, template=template, lines=lines)
    if dimension_normal is None:
        return None

    if dimension_normal[0] < -0.0001:
        return "right"
    if dimension_normal[0] > 0.0001:
        return "left"

    return None


def get_fixed_label_side(label: str, hook: dict, template: dict, lines: dict[str, dict[str, Point]]) -> str:
    fixed_side = hook.get("label_fixed_side")
    if fixed_side in ("left", "right"):
        return fixed_side

    dimension_opposite_side = get_label_side_opposite_dimension(hook=hook, template=template, lines=lines)
    if dimension_opposite_side:
        return dimension_opposite_side

    normalized_label = label.strip().upper()
    if normalized_label == "Z1":
        return "left"
    if normalized_label == "Z2":
        return "right"

    return "right"


def add_fixed_hook_label(msp, label: str, geometry: dict[str, Any], hook: dict, template: dict, lines: dict[str, dict[str, Point]]):
    height = float(hook.get("label_height", CAD_STYLES["text"]["height"]))
    rotation = float(hook.get("label_rotation", 0))
    text_width, text_height = estimate_text_size(text=label, height=height)
    min_x, min_y, max_x, max_y = get_hook_bounds(geometry=geometry)
    gap = float(hook.get("label_fixed_gap", max(10, geometry["width"] * 4)))
    fixed_side = get_fixed_label_side(label=label, hook=hook, template=template, lines=lines)
    y = (min_y + max_y - text_height) / 2

    if fixed_side == "left":
        x = min_x - gap - text_width
    elif fixed_side == "right":
        x = max_x + gap
    else:
        raise ValueError(f"Unknown hook label fixed side: {fixed_side}")

    add_text(msp=msp, text=label, position=(x, y), height=height, rotation=rotation)


def draw_single_hook(msp, hook: dict, lines: dict[str, dict[str, Point]], template: dict, avoidance_lines: list[Segment] | None = None):
    geometry = get_single_hook_geometry(hook=hook, lines=lines, template=template)
    width = geometry["width"]
    points = [
        (geometry["p0"][0], geometry["p0"][1], 0),
        (geometry["p1"][0], geometry["p1"][1], geometry["bulge"]),
        (geometry["p2"][0], geometry["p2"][1], 0),
        (geometry["p3"][0], geometry["p3"][1], 0),
    ]

    add_rounded_profile_path(msp=msp, points=points, width=width)
    add_rounded_profile_path(
        msp=msp,
        points=[
            (geometry["inner_patch_start"][0], geometry["inner_patch_start"][1], 0),
            (geometry["inner_patch_end"][0], geometry["inner_patch_end"][1], 0),
        ],
        width=width,
    )

    label = hook.get("label")
    if label:
        add_fixed_hook_label(msp=msp, label=str(label), geometry=geometry, hook=hook, template=template, lines=lines)


def draw_hooks(msp, template: dict, lines: dict[str, dict[str, Point]], parameters: dict[str, float], avoidance_lines: list[Segment] | None = None):
    width = get_profile_width(template=template)

    for hook in template.get("hooks", []):
        hook_type = hook.get("type")

        if hook_type == "hook":
            draw_single_hook(msp=msp, hook=hook, lines=lines, template=template, avoidance_lines=avoidance_lines)
        elif hook_type == "line":
            start = resolve_point(hook["start"], parameters)
            end = resolve_point(hook["end"], parameters)
            add_rounded_profile_path(msp=msp, points=[(start[0], start[1], 0), (end[0], end[1], 0)], width=width)
        else:
            raise ValueError(f"Unknown hook type: {hook_type}")


def get_dimension_normal(start: Point, end: Point, side: str) -> Point:
    line_direction = normalize(get_vector(start, end))

    if side == "left":
        return rotate_counterclockwise(line_direction)
    if side == "right":
        return rotate_clockwise(line_direction)

    raise ValueError(f"Unknown dimension side: {side}")


def get_hook_projection_extent(geometry: dict[str, Any], normal: Point) -> float:
    base = geometry["base"]
    max_projection = 0.0

    for point in get_hook_points(geometry=geometry):
        projection = (point[0] - base[0]) * normal[0] + (point[1] - base[1]) * normal[1]
        max_projection = max(max_projection, projection)

    return max_projection + float(geometry["width"]) / 2


def get_dimension_hook_clearance(
    dim: dict,
    parameters: dict[str, float],
    normal: Point,
    template: dict,
    lines: dict[str, dict[str, Point]],
) -> tuple[float, float, float]:
    target_name = dim["target"]
    profile_width = get_profile_width(template=template)
    profile_gap = profile_width * 2
    hook_clearance = resolve_value(dim.get("hook_clearance", max(8, profile_width * 4)), parameters)
    start_gap = profile_gap
    end_gap = profile_gap
    required_offset = 0.0

    for hook in template.get("hooks", []):
        if hook.get("type") != "hook" or hook.get("attach_to") != target_name:
            continue

        geometry = get_single_hook_geometry(hook=hook, lines=lines, template=template)
        side_direction = geometry["side_direction"]

        if side_direction[0] * normal[0] + side_direction[1] * normal[1] < 0.5:
            continue

        hook_extent = get_hook_projection_extent(geometry=geometry, normal=normal)
        required_offset = max(required_offset, hook_extent + hook_clearance)

        if geometry["position"] == "start":
            start_gap = max(start_gap, hook_extent)
        elif geometry["position"] == "end":
            end_gap = max(end_gap, hook_extent)

    return start_gap, end_gap, required_offset


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

    profile_gap = get_profile_width(template=template) * 2 if template is not None else CAD_STYLES["profile"]["width"] * 2
    start_gap = profile_gap
    end_gap = profile_gap

    if template is not None:
        start_gap, end_gap, required_offset = get_dimension_hook_clearance(
            dim=dim,
            parameters=parameters,
            normal=normal,
            template=template,
            lines=lines,
        )
        offset = max(offset, required_offset)

    d1 = offset_point(p1, normal, offset)
    d2 = offset_point(p2, normal, offset)

    return {
        "p1": p1,
        "p2": p2,
        "normal": normal,
        "d1": d1,
        "d2": d2,
        "e1_start": offset_point(p1, normal, min(start_gap, offset)),
        "e1_end": d1,
        "e2_start": offset_point(p2, normal, min(end_gap, offset)),
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
            geometry = get_single_hook_geometry(hook=hook, lines=lines, template=template)
            obstacles.extend(get_single_hook_segments(geometry=geometry))
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
            obstacles.extend(get_angle_mark_segments(mark=mark, parameters=parameters, lines=lines))

    return obstacles


def generate_dxf(template: dict, output_path: Path, parameters: dict[str, float]) -> None:
    doc = setup_document()
    msp = doc.modelspace()
    lines = build_named_lines(template=template, parameters=parameters)
    obstacle_lines = build_obstacle_lines(template=template, parameters=parameters, lines=lines)

    draw_profile(msp=msp, template=template, lines=lines, parameters=parameters)
    draw_hooks(msp=msp, template=template, lines=lines, parameters=parameters, avoidance_lines=obstacle_lines)
    draw_dimensions(msp=msp, template=template, parameters=parameters, lines=lines)
    draw_markers(msp=msp, template=template, parameters=parameters, lines=lines)
    draw_angle_marks(msp=msp, template=template, parameters=parameters, lines=lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
