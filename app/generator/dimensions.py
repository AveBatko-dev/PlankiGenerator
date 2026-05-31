from typing import Any

from config import CAD_STYLES
from .drawing import add_text, add_tick, get_tick_segment
from .formulas import fmt, resolve_value
from .geometry import get_angle_degrees, get_vector, normalize, offset_point, rotate_clockwise, rotate_counterclockwise
from .hooks import get_actual_hook_points, get_single_hook_geometry
from .settings import DIMENSION_HOOK_CLEARANCE_FACTOR, get_dimension_attribs, get_hook_width, get_main_profile_width
from .types import Point, Segment


def get_dimension_normal(start: Point, end: Point, side: str) -> Point:
    line_direction = normalize(get_vector(start, end))

    if side == "left":
        return rotate_counterclockwise(line_direction)
    if side == "right":
        return rotate_clockwise(line_direction)

    raise ValueError(f"Unknown dimension side: {side}")


def get_hook_projection_extent(geometry: dict[str, Any], normal: Point) -> float:
    base_point = geometry["base"]
    max_projection = 0.0

    for point in get_actual_hook_points(geometry=geometry):
        projection = (point[0] - base_point[0]) * normal[0] + (point[1] - base_point[1]) * normal[1]
        max_projection = max(max_projection, projection)

    return max_projection + float(geometry["width"]) / 2


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


def get_dimension_hook_data(
    dim: dict,
    parameters: dict[str, float],
    normal: Point,
    line_direction: Point,
    template: dict,
    lines: dict[str, dict[str, Point]],
) -> tuple[float, float, float, float, float]:
    target_name = dim["target"]
    profile_width = get_main_profile_width(template=template)
    profile_gap = profile_width * 2
    hook_clearance = resolve_value(dim.get("hook_clearance", max(8, profile_width * 4)), parameters) * DIMENSION_HOOK_CLEARANCE_FACTOR
    hook_line_clearance = resolve_value(dim.get("hook_line_clearance", max(1, get_hook_width(template=template) * 0.5)), parameters)
    start_gap = profile_gap
    end_gap = profile_gap
    required_offset = 0.0
    start_line_extend = 0.0
    end_line_extend = 0.0

    for hook in template.get("hooks", []):
        if hook.get("type") != "hook" or hook.get("attach_to") != target_name:
            continue

        geometry = get_single_hook_geometry(hook=hook, lines=lines, template=template)
        line_extend = get_hook_line_extension(geometry=geometry, line_direction=line_direction) + hook_line_clearance

        if geometry["position"] == "start":
            start_line_extend = max(start_line_extend, line_extend)
        elif geometry["position"] == "end":
            end_line_extend = max(end_line_extend, line_extend)

        side_direction = geometry["side_direction"]
        if side_direction[0] * normal[0] + side_direction[1] * normal[1] < 0.5:
            continue

        hook_extent = get_hook_projection_extent(geometry=geometry, normal=normal)
        required_offset = max(required_offset, hook_extent + hook_clearance)

        if geometry["position"] == "start":
            start_gap = max(start_gap, hook_extent)
        elif geometry["position"] == "end":
            end_gap = max(end_gap, hook_extent)

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

    profile_gap = get_main_profile_width(template=template) * 2 if template is not None else CAD_STYLES["profile"]["width"] * 2
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

    attribs = get_dimension_attribs()
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
