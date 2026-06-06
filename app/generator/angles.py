import math

from config import CAD_STYLES
from .drawing import add_angle_tick, add_centered_text, get_angle_tick_segment
from .formulas import fmt, resolve_value
from .geometry import get_angle_degrees, get_arc_segments
from .settings import get_dimension_attribs
from .types import Point, Segment

ANGLE_TEXT_LINEWEIGHT = 40


def get_angle_mark_geometry(mark: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    param_name = mark["param"]
    if param_name not in parameters:
        raise ValueError(f"Missing angle parameter: {param_name}")

    line_1_name = mark["line_1"]
    line_2_name = mark["line_2"]
    if line_1_name not in lines:
        raise ValueError(f"Angle line not found: {line_1_name}")
    if line_2_name not in lines:
        raise ValueError(f"Angle line not found: {line_2_name}")

    line_1 = lines[line_1_name]
    line_2 = lines[line_2_name]

    center_point = mark.get("center_point", "end")
    if center_point not in ("start", "end"):
        raise ValueError(f"Unknown angle center_point: {center_point}")

    line_2_point = mark.get("line_2_point", "end")
    if line_2_point not in ("start", "end"):
        raise ValueError(f"Unknown angle line_2_point: {line_2_point}")

    center = line_1[center_point]
    radius = resolve_value(mark.get("radius", 28), parameters)

    line_1_ray_point = line_1["start"] if center_point == "end" else line_1["end"]
    line_2_ray_point = line_2[line_2_point]

    angle_1 = get_angle_degrees(center, line_1_ray_point)
    angle_2 = get_angle_degrees(center, line_2_ray_point)

    draw_angle_1 = angle_1
    draw_angle_2 = angle_2

    while draw_angle_2 < draw_angle_1:
        draw_angle_2 += 360

    if mark.get("arc_side") == "other":
        draw_angle_1, draw_angle_2 = draw_angle_2, draw_angle_1 + 360

    return center, radius, draw_angle_1, draw_angle_2


def get_angle_mark_segments(mark: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]) -> list[Segment]:
    center, radius, draw_angle_1, draw_angle_2 = get_angle_mark_geometry(mark=mark, parameters=parameters, lines=lines)
    angle_tick_size = resolve_value(mark.get("tick_size", 15), parameters)

    return (
        get_arc_segments(center=center, radius=radius, start_angle=draw_angle_1, end_angle=draw_angle_2)
        + [get_angle_tick_segment(center=center, radius=radius, angle_degrees=draw_angle_1, size=angle_tick_size)]
        + [get_angle_tick_segment(center=center, radius=radius, angle_degrees=draw_angle_2, size=angle_tick_size)]
    )


def draw_angle_marks(msp, template: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    for mark in template.get("angle_marks", []):
        if not mark.get("enabled", False):
            continue

        center, radius, draw_angle_1, draw_angle_2 = get_angle_mark_geometry(
            mark=mark,
            parameters=parameters,
            lines=lines
        )

        attribs = get_dimension_attribs()

        msp.add_arc(
            center=center,
            radius=radius,
            start_angle=draw_angle_1,
            end_angle=draw_angle_2,
            dxfattribs=attribs
        )

        angle_tick_size = resolve_value(mark.get("tick_size", 15), parameters)

        add_angle_tick(
            msp=msp,
            center=center,
            radius=radius,
            angle_degrees=draw_angle_1,
            size=angle_tick_size
        )

        add_angle_tick(
            msp=msp,
            center=center,
            radius=radius,
            angle_degrees=draw_angle_2,
            size=angle_tick_size
        )

        mid_angle_degrees = (draw_angle_1 + draw_angle_2) / 2
        mid_angle = math.radians(mid_angle_degrees)

        text_radius = radius + resolve_value(mark.get("text_offset", 8), parameters)

        text_position = (
            center[0] + math.cos(mid_angle) * text_radius,
            center[1] + math.sin(mid_angle) * text_radius
        )

        add_centered_text(
            msp=msp,
            text=f"{fmt(parameters[mark['param']])}°",
            position=text_position,
            height=mark.get("text_height", CAD_STYLES["text"]["height"]),
            rotation=mark.get("text_rotation", 0),
            lineweight=mark.get("text_lineweight", ANGLE_TEXT_LINEWEIGHT),
        )
