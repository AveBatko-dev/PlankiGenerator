from .formulas import resolve_value
from .geometry import get_left_normal, get_right_normal, get_vector, normalize, offset_point
from .settings import get_dimension_attribs
from .types import Point, Segment


def get_triangle_marker_points(tip: Point, line_direction: Point, side_direction: Point, height: float = 12, depth: float = 10) -> list[Point]:
    dx, dy = normalize(line_direction)
    sx, sy = normalize(side_direction)
    base_center = (tip[0] + sx * depth, tip[1] + sy * depth)
    half_height = height / 2
    p1 = (base_center[0] - dx * half_height, base_center[1] - dy * half_height)
    p2 = tip
    p3 = (base_center[0] + dx * half_height, base_center[1] + dy * half_height)
    return [p1, p2, p3]


def get_triangle_marker_segments(tip: Point, line_direction: Point, side_direction: Point, height: float = 12, depth: float = 10) -> list[Segment]:
    p1, p2, p3 = get_triangle_marker_points(tip=tip, line_direction=line_direction, side_direction=side_direction, height=height, depth=depth)
    return [(p1, p2), (p2, p3), (p3, p1)]


def add_triangle_marker(msp, tip: Point, line_direction: Point, side_direction: Point, height: float = 12, depth: float = 10):
    p1, p2, p3 = get_triangle_marker_points(tip=tip, line_direction=line_direction, side_direction=side_direction, height=height, depth=depth)
    msp.add_lwpolyline(
        [p1, p2, p3, p1],
        dxfattribs=get_dimension_attribs(),
    )


def get_marker_segments(marker: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]) -> list[Segment]:
    target_name = marker["target"]
    line = lines[target_name]
    start = line["start"]
    end = line["end"]
    line_vector = get_vector(start, end)
    line_direction = normalize(line_vector)

    position = marker.get("position", 0.5)
    if position == "middle":
        position_value = 0.5
    elif position == "start":
        position_value = 0
    elif position == "end":
        position_value = 1
    else:
        position_value = resolve_value(position, parameters)

    point = (start[0] + line_vector[0] * position_value, start[1] + line_vector[1] * position_value)
    side = marker.get("side", "left")
    if side == "left":
        side_direction = get_left_normal(start, end)
    elif side == "right":
        side_direction = get_right_normal(start, end)
    else:
        raise ValueError(f"Unknown marker side: {side}")

    offset = resolve_value(marker.get("offset", 2), parameters)
    tip = offset_point(point=point, normal=side_direction, distance=offset)
    height = resolve_value(marker.get("height", 12), parameters)
    depth = resolve_value(marker.get("depth", 10), parameters)
    return get_triangle_marker_segments(tip=tip, line_direction=line_direction, side_direction=side_direction, height=height, depth=depth)


def draw_markers(msp, template: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    for marker in template.get("markers", []):
        marker_type = marker.get("type")
        if marker_type not in ("triangle", "thickness_triangle"):
            raise ValueError(f"Unknown marker type: {marker_type}")

        target_name = marker["target"]
        if target_name not in lines:
            raise ValueError(f"Marker target line not found: {target_name}")

        line = lines[target_name]
        start = line["start"]
        end = line["end"]
        line_vector = get_vector(start, end)
        line_direction = normalize(line_vector)

        position = marker.get("position", 0.5)
        if position == "middle":
            position_value = 0.5
        elif position == "start":
            position_value = 0
        elif position == "end":
            position_value = 1
        else:
            position_value = resolve_value(position, parameters)

        point = (start[0] + line_vector[0] * position_value, start[1] + line_vector[1] * position_value)
        side = marker.get("side", "left")
        if side == "left":
            side_direction = get_left_normal(start, end)
        elif side == "right":
            side_direction = get_right_normal(start, end)
        else:
            raise ValueError(f"Unknown marker side: {side}")

        offset = resolve_value(marker.get("offset", 2), parameters)
        tip = offset_point(point=point, normal=side_direction, distance=offset)
        height = resolve_value(marker.get("height", 12), parameters)
        depth = resolve_value(marker.get("depth", 10), parameters)

        add_triangle_marker(msp=msp, tip=tip, line_direction=line_direction, side_direction=side_direction, height=height, depth=depth)
