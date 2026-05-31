from typing import Any
import math

from config import CAD_STYLES
from .drawing import add_rounded_profile_path, add_text, estimate_text_size
from .formulas import resolve_point
from .geometry import (
    get_distance,
    get_vector,
    normalize,
    rotate_clockwise,
    rotate_counterclockwise,
    rotate_vector,
    get_semicircle_segments,
)
from .settings import HOOK_SPAN_FACTOR, get_hook_width
from .types import Point, Segment


def get_actual_hook_arc_points(geometry: dict[str, Any], steps: int = 24) -> list[Point]:
    start = geometry["p1"]
    end = geometry["p2"]
    bulge = float(geometry["bulge"])

    if bulge == 0:
        return [start, end]

    chord_length = get_distance(start, end)
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


def get_single_hook_geometry(hook: dict, lines: dict[str, dict[str, Point]], template: dict) -> dict[str, Any]:
    attach_to = hook["attach_to"]
    position = hook["position"]

    if attach_to not in lines:
        raise ValueError(f"Hook target line not found: {attach_to}")

    line = lines[attach_to]
    line_start = line["start"]
    line_end = line["end"]
    width = get_hook_width(template=template)
    length = float(hook["length"])
    angle = float(hook.get("angle", 90))

    if angle != 90:
        raise ValueError("Only 90 degree hooks are supported for now")

    line_direction = normalize(get_vector(line_start, line_end))
    hook_gap = float(hook.get("gap", length)) * HOOK_SPAN_FACTOR
    tail_length = float(hook.get("tail_length", length))
    join_overlap = width * 1.6
    inner_join_overlap = width * 0.28
    arc_steps = int(hook.get("arc_obstacle_steps", 16))

    if position == "start":
        base_point = line_start
        side = hook.get("side", "right")

        if side == "right":
            side_direction = rotate_clockwise(line_direction)
            bulge = 1
        elif side == "left":
            side_direction = rotate_counterclockwise(line_direction)
            bulge = -1
        else:
            raise ValueError(f"Unknown hook side: {side}")

        p0 = (base_point[0] + line_direction[0] * join_overlap, base_point[1] + line_direction[1] * join_overlap)
        p1 = base_point
        p2 = (base_point[0] + side_direction[0] * hook_gap, base_point[1] + side_direction[1] * hook_gap)
        p3 = (p2[0] + line_direction[0] * tail_length, p2[1] + line_direction[1] * tail_length)
        inner_patch_start = (p2[0] - line_direction[0] * inner_join_overlap, p2[1] - line_direction[1] * inner_join_overlap)
        arc_side_direction = line_direction

    elif position == "end":
        base_point = line_end
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
        p0 = (base_point[0] + back_direction[0] * join_overlap, base_point[1] + back_direction[1] * join_overlap)
        p1 = base_point
        p2 = (base_point[0] + side_direction[0] * hook_gap, base_point[1] + side_direction[1] * hook_gap)
        p3 = (p2[0] + back_direction[0] * tail_length, p2[1] + back_direction[1] * tail_length)
        inner_patch_start = (p2[0] - back_direction[0] * inner_join_overlap, p2[1] - back_direction[1] * inner_join_overlap)
        arc_side_direction = back_direction

    else:
        raise ValueError(f"Unknown hook position: {position}")

    return {
        "width": width,
        "base": base_point,
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


def get_actual_hook_points(geometry: dict[str, Any]) -> list[Point]:
    return [
        geometry["p0"],
        geometry["p1"],
        *get_actual_hook_arc_points(geometry=geometry, steps=int(geometry.get("arc_steps", 24))),
        geometry["p2"],
        geometry["p3"],
        geometry["inner_patch_start"],
        geometry["inner_patch_end"],
    ]


def get_hook_bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    points = get_actual_hook_points(geometry=geometry)
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


def get_default_label_direction(label: str, geometry: dict[str, Any]) -> Point:
    normalized_label = label.strip().upper()
    line_direction = geometry["line_direction"]
    side_direction = geometry["side_direction"]

    if normalized_label == "Z1":
        return normalize((side_direction[0] - line_direction[0], side_direction[1] - line_direction[1]))
    if normalized_label == "Z2":
        return normalize((side_direction[0] + line_direction[0], side_direction[1] + line_direction[1]))

    return side_direction


def get_fixed_label_direction(label: str, geometry: dict[str, Any], hook: dict, template: dict, lines: dict[str, dict[str, Point]]) -> Point:
    fixed_direction = hook.get("label_fixed_direction")
    if fixed_direction == "line_left":
        return rotate_counterclockwise(geometry["line_direction"])
    if fixed_direction == "line_right":
        return rotate_clockwise(geometry["line_direction"])
    if fixed_direction == "hook_side":
        return geometry["side_direction"]
    if fixed_direction == "opposite_hook_side":
        side_direction = geometry["side_direction"]
        return (-side_direction[0], -side_direction[1])
    if fixed_direction == "opposite_dimension":
        dimension_normal = get_dimension_normal_for_hook(hook=hook, template=template, lines=lines)
        if dimension_normal is not None:
            return (-dimension_normal[0], -dimension_normal[1])

    fixed_side = hook.get("label_fixed_side")
    if fixed_side == "left":
        return (-1, 0)
    if fixed_side == "right":
        return (1, 0)

    return get_default_label_direction(label=label, geometry=geometry)


def get_label_text_position(anchor: Point, direction: Point, text_width: float, text_height: float) -> Point:
    direction = normalize(direction)
    x = anchor[0]
    y = anchor[1]

    if direction[0] < -0.15:
        x -= text_width
    elif abs(direction[0]) <= 0.15:
        x -= text_width / 2

    if direction[1] < -0.15:
        y -= text_height
    elif abs(direction[1]) <= 0.15:
        y -= text_height / 2

    return x, y


def add_fixed_hook_label(msp, label: str, geometry: dict[str, Any], hook: dict, template: dict, lines: dict[str, dict[str, Point]]):
    height = float(hook.get("label_height", CAD_STYLES["text"]["height"]))
    rotation = float(hook.get("label_rotation", 0))
    text_width, text_height = estimate_text_size(text=label, height=height)
    label_direction = get_fixed_label_direction(label=label, geometry=geometry, hook=hook, template=template, lines=lines)
    gap = float(hook.get("label_fixed_gap", max(10, geometry["width"] * 4)))
    base = geometry["base"]
    anchor = (base[0] + label_direction[0] * gap, base[1] + label_direction[1] * gap)
    label_position = get_label_text_position(anchor=anchor, direction=label_direction, text_width=text_width, text_height=text_height)

    add_text(msp=msp, text=label, position=label_position, height=height, rotation=rotation)


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
    width = get_hook_width(template=template)

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
