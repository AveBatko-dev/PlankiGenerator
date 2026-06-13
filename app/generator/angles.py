import math

from config import CAD_STYLES
from .drawing import add_angle_tick, add_centered_text, get_angle_tick_segment
from .formulas import fmt, resolve_value
from .geometry import get_angle_degrees, get_arc_segments, get_vector, normalize
from .labels import point_to_segment_distance, segments_intersect
from .settings import get_dimension_attribs
from .types import Point, Segment


ANGLE_TEXT_LINEWEIGHT = 40

DEFAULT_SELECTED_POINT_GAP = 4
DEFAULT_EXTENSION_LENGTH = 28
DEFAULT_MAX_EXTENSION_LENGTH = 55
DEFAULT_EXTENSION_STEP = 4
DEFAULT_OBSTACLE_CLEARANCE = 4


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


def segment_to_segment_distance(first: Segment, second: Segment) -> float:
    if segments_intersect(first, second):
        return 0.0

    return min(
        point_to_segment_distance(first[0], second),
        point_to_segment_distance(first[1], second),
        point_to_segment_distance(second[0], first),
        point_to_segment_distance(second[1], first),
    )


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


def get_angle_base_radius(
    mark: dict,
    parameters: dict[str, float],
    line_1_ray: dict,
    line_2_ray: dict,
) -> float:
    radius_mode = mark.get("radius_mode")

    if radius_mode == "near_extension_tip":
        radius_from_line = mark.get("radius_from_line", "line_2")

        if radius_from_line == "line_1":
            selected_distance = line_1_ray["selected_distance"]
        elif radius_from_line == "line_2":
            selected_distance = line_2_ray["selected_distance"]
        else:
            raise ValueError(f"Unknown angle radius_from_line: {radius_from_line}")

        extension_length = resolve_value(
            mark.get("extension_length", DEFAULT_EXTENSION_LENGTH),
            parameters
        )
        selected_point_gap = resolve_value(
            mark.get("selected_point_gap", DEFAULT_SELECTED_POINT_GAP),
            parameters
        )

        return selected_distance + extension_length - selected_point_gap

    if "selected_point_gap" in mark:
        radius_from_line = mark.get("radius_from_line", "line_2")

        if radius_from_line == "line_1":
            selected_distance = line_1_ray["selected_distance"]
        elif radius_from_line == "line_2":
            selected_distance = line_2_ray["selected_distance"]
        else:
            raise ValueError(f"Unknown angle radius_from_line: {radius_from_line}")

        return selected_distance + resolve_value(
            mark.get("selected_point_gap", DEFAULT_SELECTED_POINT_GAP),
            parameters
        )

    return resolve_value(mark.get("radius", 28), parameters)


def get_angle_arc_and_tick_segments(data: dict, tick_size: float) -> list[Segment]:
    center = data["center"]
    radius = data["radius"]
    draw_angle_1 = data["draw_angle_1"]
    draw_angle_2 = data["draw_angle_2"]

    return (
        get_arc_segments(
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
                size=tick_size
            )
        ]
        + [
            get_angle_tick_segment(
                center=center,
                radius=radius,
                angle_degrees=draw_angle_2,
                size=tick_size
            )
        ]
    )


def get_rotated_rect_segments(
    center: Point,
    width: float,
    height: float,
    rotation_degrees: float
) -> list[Segment]:
    angle = math.radians(rotation_degrees)
    ux = math.cos(angle)
    uy = math.sin(angle)
    vx = -math.sin(angle)
    vy = math.cos(angle)

    half_width = width / 2
    half_height = height / 2

    corners = [
        (
            center[0] - ux * half_width - vx * half_height,
            center[1] - uy * half_width - vy * half_height
        ),
        (
            center[0] + ux * half_width - vx * half_height,
            center[1] + uy * half_width - vy * half_height
        ),
        (
            center[0] + ux * half_width + vx * half_height,
            center[1] + uy * half_width + vy * half_height
        ),
        (
            center[0] - ux * half_width + vx * half_height,
            center[1] - uy * half_width + vy * half_height
        ),
    ]

    return [
        (corners[0], corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    ]


def get_angle_text_segments(
    mark: dict,
    parameters: dict[str, float],
    data: dict
) -> list[Segment]:
    if not mark.get("check_text_clearance", True):
        return []

    center = data["center"]
    radius = data["radius"]
    draw_angle_1 = data["draw_angle_1"]
    draw_angle_2 = data["draw_angle_2"]

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

    text = get_angle_text(mark=mark, parameters=parameters)
    text_height = resolve_value(mark.get("text_height", CAD_STYLES["text"]["height"]), parameters)

    width = max(text_height, len(text) * text_height * 0.62)
    height = text_height * 1.1

    padding = resolve_value(mark.get("text_clearance_padding", 2), parameters)

    return get_rotated_rect_segments(
        center=text_position,
        width=width + padding * 2,
        height=height + padding * 2,
        rotation_degrees=text_rotation
    )


def get_angle_dimension_obstacles(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    template: dict | None,
) -> list[Segment]:
    if template is None:
        return []

    from .dimensions import get_parallel_dimension_segments

    ignored_names = set(mark.get("ignore_dimension_names", []))
    obstacles: list[Segment] = []

    for dim in template.get("dimensions", []):
        if dim.get("type") != "parallel_to_line":
            continue

        if dim.get("name") in ignored_names:
            continue

        dimension_segments = get_parallel_dimension_segments(
            dim=dim,
            parameters=parameters,
            lines=lines,
            template=template
        )

        if not dimension_segments:
            continue

        if mark.get("avoid_dimension_extensions", False):
            obstacles.extend(dimension_segments)
        else:
            obstacles.append(dimension_segments[0])
            obstacles.extend(dimension_segments[3:])

    return obstacles


def has_angle_obstacle_clearance(
    angle_segments: list[Segment],
    obstacles: list[Segment],
    clearance: float,
) -> bool:
    for angle_segment in angle_segments:
        for obstacle in obstacles:
            if segment_to_segment_distance(angle_segment, obstacle) < clearance:
                return False

    return True


def get_angle_extension_needed_distance(
    mark: dict,
    parameters: dict[str, float],
    data: dict,
    line_key: str
) -> float:
    ray = data[f"{line_key}_ray"]
    selected_distance = ray["selected_distance"]
    radius = data["radius"]

    radius_mode = mark.get("radius_mode")

    if radius_mode == "near_extension_tip":
        selected_point_gap = resolve_value(
            mark.get("selected_point_gap", DEFAULT_SELECTED_POINT_GAP),
            parameters
        )
        return max(selected_distance, radius + selected_point_gap)

    if "extension_tip_gap" in mark:
        return radius + resolve_value(mark["extension_tip_gap"], parameters)

    if "extension_overhang" in mark:
        return radius + resolve_value(mark["extension_overhang"], parameters)

    tick_size = resolve_value(mark.get("tick_size", 15), parameters)
    return radius + max(10, tick_size * 0.8)


def get_angle_extension_segments_from_data(
    mark: dict,
    parameters: dict[str, float],
    data: dict
) -> list[Segment]:
    if not mark.get("auto_extensions", False):
        return []

    extension_lines = mark.get("extension_lines", ["line_1", "line_2"])
    center = data["center"]

    segments: list[Segment] = []

    for line_key in extension_lines:
        if line_key not in ("line_1", "line_2"):
            raise ValueError(f"Unknown angle extension line: {line_key}")

        ray = data[f"{line_key}_ray"]
        selected_distance = ray["selected_distance"]
        needed_distance = get_angle_extension_needed_distance(
            mark=mark,
            parameters=parameters,
            data=data,
            line_key=line_key
        )

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


def get_full_angle_check_segments(
    mark: dict,
    parameters: dict[str, float],
    data: dict
) -> list[Segment]:
    tick_size = resolve_value(mark.get("tick_size", 15), parameters)

    return (
        get_angle_extension_segments_from_data(
            mark=mark,
            parameters=parameters,
            data=data
        )
        + get_angle_arc_and_tick_segments(
            data=data,
            tick_size=tick_size
        )
        + get_angle_text_segments(
            mark=mark,
            parameters=parameters,
            data=data
        )
    )


def fit_angle_layout_to_obstacles(
    mark: dict,
    parameters: dict[str, float],
    data: dict,
    lines: dict[str, dict[str, Point]],
    template: dict | None,
) -> dict:
    if not mark.get("auto_radius_clearance", False):
        return data

    obstacles = get_angle_dimension_obstacles(
        mark=mark,
        parameters=parameters,
        lines=lines,
        template=template
    )

    if not obstacles:
        return data

    clearance = resolve_value(
        mark.get("obstacle_clearance", DEFAULT_OBSTACLE_CLEARANCE),
        parameters
    )
    step = resolve_value(
        mark.get("extension_step", mark.get("radius_step", DEFAULT_EXTENSION_STEP)),
        parameters
    )

    if step <= 0:
        raise ValueError("Angle radius_step / extension_step must be greater than zero")

    radius_mode = mark.get("radius_mode")

    if radius_mode == "near_extension_tip":
        radius_from_line = mark.get("radius_from_line", "line_2")

        if radius_from_line == "line_1":
            selected_distance = data["line_1_ray"]["selected_distance"]
        elif radius_from_line == "line_2":
            selected_distance = data["line_2_ray"]["selected_distance"]
        else:
            raise ValueError(f"Unknown angle radius_from_line: {radius_from_line}")

        min_extension_length = resolve_value(
            mark.get("extension_length", DEFAULT_EXTENSION_LENGTH),
            parameters
        )
        max_extension_length = resolve_value(
            mark.get("max_extension_length", DEFAULT_MAX_EXTENSION_LENGTH),
            parameters
        )
        selected_point_gap = resolve_value(
            mark.get("selected_point_gap", DEFAULT_SELECTED_POINT_GAP),
            parameters
        )

        if max_extension_length < min_extension_length:
            max_extension_length = min_extension_length

        attempts = int((max_extension_length - min_extension_length) / step)

        fallback_data = data

        for attempt in range(attempts + 1):
            extension_length = min_extension_length + attempt * step
            radius = selected_distance + extension_length - selected_point_gap

            candidate = {
                **data,
                "radius": radius,
                "resolved_extension_length": extension_length
            }

            angle_segments = get_full_angle_check_segments(
                mark=mark,
                parameters=parameters,
                data=candidate
            )

            if has_angle_obstacle_clearance(
                angle_segments=angle_segments,
                obstacles=obstacles,
                clearance=clearance
            ):
                return candidate

            fallback_data = candidate

        return fallback_data

    max_radius_shift = resolve_value(mark.get("max_radius_shift", 20), parameters)
    base_radius = data["radius"]
    attempts = int(max(0, max_radius_shift) / step)

    fallback_data = data

    for attempt in range(attempts + 1):
        radius = base_radius + attempt * step
        candidate = {
            **data,
            "radius": radius
        }

        angle_segments = get_full_angle_check_segments(
            mark=mark,
            parameters=parameters,
            data=candidate
        )

        if has_angle_obstacle_clearance(
            angle_segments=angle_segments,
            obstacles=obstacles,
            clearance=clearance
        ):
            return candidate

        fallback_data = candidate

    return fallback_data


def get_angle_mark_data(
    mark: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    template: dict | None = None,
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

    radius = get_angle_base_radius(
        mark=mark,
        parameters=parameters,
        line_1_ray=line_1_ray,
        line_2_ray=line_2_ray
    )

    angle_1 = line_1_ray["angle"]
    angle_2 = line_2_ray["angle"]

    draw_angle_1 = angle_1
    draw_angle_2 = angle_2

    while draw_angle_2 < draw_angle_1:
        draw_angle_2 += 360

    if mark.get("arc_side") == "other":
        draw_angle_1, draw_angle_2 = draw_angle_2, draw_angle_1 + 360

    data = {
        "center": center,
        "radius": radius,
        "draw_angle_1": draw_angle_1,
        "draw_angle_2": draw_angle_2,
        "line_1_ray": line_1_ray,
        "line_2_ray": line_2_ray
    }

    return fit_angle_layout_to_obstacles(
        mark=mark,
        parameters=parameters,
        data=data,
        lines=lines,
        template=template
    )


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
    lines: dict[str, dict[str, Point]],
    template: dict | None = None,
) -> list[Segment]:
    data = get_angle_mark_data(
        mark=mark,
        parameters=parameters,
        lines=lines,
        template=template
    )

    tick_size = resolve_value(mark.get("tick_size", 15), parameters)

    return (
        get_angle_extension_segments_from_data(
            mark=mark,
            parameters=parameters,
            data=data
        )
        + get_angle_arc_and_tick_segments(
            data=data,
            tick_size=tick_size
        )
        + get_angle_text_segments(
            mark=mark,
            parameters=parameters,
            data=data
        )
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
            lines=lines,
            template=template
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
