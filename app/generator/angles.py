import math

from config import CAD_STYLES
from .drawing import add_angle_tick, add_centered_text, get_angle_tick_segment
from .formulas import fmt, resolve_value
from .geometry import get_angle_degrees, get_arc_segments, get_vector, normalize
from .settings import get_dimension_attribs
from .types import Point, Segment


ANGLE_TEXT_LINEWEIGHT = 40


def make_angle_text_readable(rotation: float) -> float:
    normalized = rotation % 360

    if 90 < normalized < 270:
        rotation += 180

    return rotation % 360


def get_angle_text_rotation(mark: dict, mid_angle_degrees: float) -> float:
    text_rotation = mark.get("text_rotation", "auto")

    if text_rotation == "auto":
        tangent_rotation = mid_angle_degrees + 90
        return make_angle_text_readable(tangent_rotation)

    if text_rotation == "horizontal":
        return 0

    return make_angle_text_readable(float(text_rotation))


def get_angle_text(mark: dict, parameters: dict[str, float]) -> str:
    if "label" in mark:
        return str(mark["label"])

    return f"{fmt(parameters[mark['param']])}°"


def get_distance(first: Point, second: Point) -> float:
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    return (dx ** 2 + dy ** 2) ** 0.5


def get_direction_angle(direction: Point) -> float:
    angle = math.degrees(math.atan2(direction[1], direction[0]))

    if angle < 0:
        angle += 360

    return angle


def get_line_direction_by_selected_point(
    line: dict[str, Point],
    selected_point_name: str
) -> Point:
    if selected_point_name == "start":
        selected = line["start"]
        other = line["end"]
    elif selected_point_name == "end":
        selected = line["end"]
        other = line["start"]
    else:
        raise ValueError(f"Unknown line point: {selected_point_name}")

    return normalize(get_vector(other, selected))


def get_line_ray_data(
    line: dict[str, Point],
    center: Point,
    selected_point_name: str,
    mode: str
) -> dict:
    if selected_point_name not in ("start", "end"):
        raise ValueError(f"Unknown line point: {selected_point_name}")

    selected_point = line[selected_point_name]

    if mode == "from_center":
        direction = normalize(get_vector(center, selected_point))
        angle = get_angle_degrees(center, selected_point)

        return {
            "selected_point": selected_point,
            "direction": direction,
            "angle": angle,
            "selected_distance": get_distance(center, selected_point)
        }

    if mode == "parallel":
        direction = get_line_direction_by_selected_point(
            line=line,
            selected_point_name=selected_point_name
        )
        angle = get_direction_angle(direction)

        return {
            "selected_point": selected_point,
            "direction": direction,
            "angle": angle,
            "selected_distance": get_distance(center, selected_point)
        }

    raise ValueError(f"Unknown angle line mode: {mode}")


def get_angle_mark_data(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
) -> dict:
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

    line_1_point = mark.get(
        "line_1_point",
        "start" if center_point == "end" else "end"
    )

    line_1_mode = mark.get("line_1_mode", "from_center")
    line_2_mode = mark.get("line_2_mode", "from_center")

    line_1_ray = get_line_ray_data(
        line=line_1,
        center=center,
        selected_point_name=line_1_point,
        mode=line_1_mode
    )

    line_2_ray = get_line_ray_data(
        line=line_2,
        center=center,
        selected_point_name=line_2_point,
        mode=line_2_mode
    )

    angle_1 = line_1_ray["angle"]
    angle_2 = line_2_ray["angle"]

    draw_angle_1 = angle_1
    draw_angle_2 = angle_2

    while draw_angle_2 < draw_angle_1:
        draw_angle_2 += 360

    if mark.get("arc_side") == "other":
        draw_angle_1, draw_angle_2 = draw_angle_2, draw_angle_1 + 360

    return {
        "center": center,
        "radius": radius,
        "draw_angle_1": draw_angle_1,
        "draw_angle_2": draw_angle_2,
        "line_1_ray": line_1_ray,
        "line_2_ray": line_2_ray
    }


def get_angle_mark_geometry(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
):
    data = get_angle_mark_data(
        mark=mark,
        parameters=parameters,
        lines=lines
    )

    return (
        data["center"],
        data["radius"],
        data["draw_angle_1"],
        data["draw_angle_2"]
    )


def get_angle_extension_segments_from_data(
    mark: dict,
    parameters: dict[str, float],
    data: dict
) -> list[Segment]:
    if not mark.get("auto_extensions", False):
        return []

    extension_lines = mark.get("extension_lines", ["line_1", "line_2"])
    extension_overhang = resolve_value(mark.get("extension_overhang", 10), parameters)
    tick_size = resolve_value(mark.get("tick_size", 15), parameters)

    center = data["center"]
    radius = data["radius"]

    needed_distance = radius + max(extension_overhang, tick_size * 0.8)

    segments: list[Segment] = []

    for line_key in extension_lines:
        if line_key not in ("line_1", "line_2"):
            raise ValueError(f"Unknown angle extension line: {line_key}")

        ray = data[f"{line_key}_ray"]
        selected_distance = ray["selected_distance"]

        if selected_distance >= needed_distance:
            continue

        direction = ray["direction"]
        selected_point = ray["selected_point"]

        extension_end = (
            center[0] + direction[0] * needed_distance,
            center[1] + direction[1] * needed_distance
        )

        if get_distance(selected_point, extension_end) > 0.001:
            segments.append((selected_point, extension_end))

    return segments


def get_angle_extension_segments(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
) -> list[Segment]:
    data = get_angle_mark_data(
        mark=mark,
        parameters=parameters,
        lines=lines
    )

    return get_angle_extension_segments_from_data(
        mark=mark,
        parameters=parameters,
        data=data
    )


def get_angle_mark_segments(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
) -> list[Segment]:
    data = get_angle_mark_data(
        mark=mark,
        parameters=parameters,
        lines=lines
    )

    center = data["center"]
    radius = data["radius"]
    draw_angle_1 = data["draw_angle_1"]
    draw_angle_2 = data["draw_angle_2"]

    angle_tick_size = resolve_value(mark.get("tick_size", 15), parameters)

    return (
        get_angle_extension_segments_from_data(
            mark=mark,
            parameters=parameters,
            data=data
        )
        + get_arc_segments(
            center=center,
            radius=radius,
            start_angle=draw_angle_1,
            end_angle=draw_angle_2
        )
        + [
            get_angle_tick_segment(
                center=center,
                radius=radius,
                angle_degrees=draw_angle_1,
                size=angle_tick_size
            )
        ]
        + [
            get_angle_tick_segment(
                center=center,
                radius=radius,
                angle_degrees=draw_angle_2,
                size=angle_tick_size
            )
        ]
    )


def draw_angle_extensions(
    msp,
    mark: dict,
    parameters: dict[str, float],
    data: dict
):
    for start, end in get_angle_extension_segments_from_data(
        mark=mark,
        parameters=parameters,
        data=data
    ):
        msp.add_line(
            start,
            end,
            dxfattribs=get_dimension_attribs()
        )


def draw_angle_marks(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
):
    for mark in template.get("angle_marks", []):
        if not mark.get("enabled", False):
            continue

        data = get_angle_mark_data(
            mark=mark,
            parameters=parameters,
            lines=lines
        )

        center = data["center"]
        radius = data["radius"]
        draw_angle_1 = data["draw_angle_1"]
        draw_angle_2 = data["draw_angle_2"]

        draw_angle_extensions(
            msp=msp,
            mark=mark,
            parameters=parameters,
            data=data
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

        text_rotation = get_angle_text_rotation(
            mark=mark,
            mid_angle_degrees=mid_angle_degrees
        )

        add_centered_text(
            msp=msp,
            text=get_angle_text(mark=mark, parameters=parameters),
            position=text_position,
            height=mark.get("text_height", CAD_STYLES["text"]["height"]),
            rotation=text_rotation,
            lineweight=mark.get("text_lineweight", ANGLE_TEXT_LINEWEIGHT),
        )
