from .formulas import resolve_value
from .geometry import get_left_normal, get_right_normal, get_vector, normalize, offset_point
from .labels import point_to_segment_distance, segments_intersect
from .settings import get_dimension_attribs
from .types import Point, Segment


AUTO_MARKER_POSITIONS = [
    0.50,
    0.45,
    0.55,
    0.40,
    0.60,
    0.35,
    0.65,
    0.30,
    0.70,
    0.25,
    0.75,
]


def points_close(first: Point, second: Point, tolerance: float = 0.001) -> bool:
    return abs(first[0] - second[0]) <= tolerance and abs(first[1] - second[1]) <= tolerance


def same_segment(first: Segment, second: Segment) -> bool:
    return (
        points_close(first[0], second[0]) and points_close(first[1], second[1])
    ) or (
        points_close(first[0], second[1]) and points_close(first[1], second[0])
    )


def segment_to_segment_distance(first: Segment, second: Segment) -> float:
    if segments_intersect(first, second):
        return 0.0

    return min(
        point_to_segment_distance(first[0], second),
        point_to_segment_distance(first[1], second),
        point_to_segment_distance(second[0], first),
        point_to_segment_distance(second[1], first),
    )


def get_triangle_marker_points(
    tip: Point,
    line_direction: Point,
    side_direction: Point,
    height: float = 12,
    depth: float = 10
) -> list[Point]:
    dx, dy = normalize(line_direction)
    sx, sy = normalize(side_direction)

    base_center = (tip[0] + sx * depth, tip[1] + sy * depth)

    half_height = height / 2
    p1 = (base_center[0] - dx * half_height, base_center[1] - dy * half_height)
    p2 = tip
    p3 = (base_center[0] + dx * half_height, base_center[1] + dy * half_height)

    return [p1, p2, p3]


def get_triangle_marker_segments(
    tip: Point,
    line_direction: Point,
    side_direction: Point,
    height: float = 12,
    depth: float = 10
) -> list[Segment]:
    p1, p2, p3 = get_triangle_marker_points(
        tip=tip,
        line_direction=line_direction,
        side_direction=side_direction,
        height=height,
        depth=depth
    )

    return [(p1, p2), (p2, p3), (p3, p1)]


def add_triangle_marker(
    msp,
    tip: Point,
    line_direction: Point,
    side_direction: Point,
    height: float = 12,
    depth: float = 10
):
    p1, p2, p3 = get_triangle_marker_points(
        tip=tip,
        line_direction=line_direction,
        side_direction=side_direction,
        height=height,
        depth=depth
    )

    msp.add_lwpolyline(
        [p1, p2, p3, p1],
        dxfattribs=get_dimension_attribs(),
    )


def get_marker_position_value(marker: dict, parameters: dict[str, float]) -> float:
    position = marker.get("position", 0.5)

    if position == "middle":
        return 0.5
    if position == "start":
        return 0.0
    if position == "end":
        return 1.0

    return resolve_value(position, parameters)


def get_manual_side_direction(marker: dict, start: Point, end: Point) -> Point:
    side = marker.get("side", "left")

    if side == "left":
        return get_left_normal(start, end)
    if side == "right":
        return get_right_normal(start, end)

    raise ValueError(f"Unknown marker side: {side}")


def choose_side_direction_for_marker(
    marker: dict,
    template: dict,
    lines: dict[str, dict[str, Point]],
    start: Point,
    end: Point
) -> Point:
    return (-1, 0)


def get_marker_candidate_segments(
    start: Point,
    line_vector: Point,
    line_direction: Point,
    side_direction: Point,
    position_value: float,
    offset: float,
    height: float,
    depth: float
) -> tuple[Point, list[Segment]]:
    point = (
        start[0] + line_vector[0] * position_value,
        start[1] + line_vector[1] * position_value
    )

    tip = offset_point(
        point=point,
        normal=side_direction,
        distance=offset
    )

    segments = get_triangle_marker_segments(
        tip=tip,
        line_direction=line_direction,
        side_direction=side_direction,
        height=height,
        depth=depth
    )

    return tip, segments


def score_marker_candidate(
    marker_segments: list[Segment],
    target_segment: Segment,
    obstacles: list[Segment],
    position_value: float
) -> float:
    score = 0.0

    score += abs(position_value - 0.5) * 100

    if position_value < 0.18:
        score += (0.18 - position_value) * 300
    if position_value > 0.82:
        score += (position_value - 0.82) * 300

    for obstacle in obstacles:
        if same_segment(obstacle, target_segment):
            continue

        min_distance = min(
            segment_to_segment_distance(marker_segment, obstacle)
            for marker_segment in marker_segments
        )

        intersects = any(
            segments_intersect(marker_segment, obstacle)
            for marker_segment in marker_segments
        )

        if intersects:
            score += 10000
            continue

        if min_distance < 1.5:
            score += (1.5 - min_distance) * 1000
        elif min_distance < 5:
            score += (5 - min_distance) * 80

    return score


def get_marker_obstacles(
    lines: dict[str, dict[str, Point]],
    avoidance_lines: list[Segment] | None = None
) -> list[Segment]:
    obstacles: list[Segment] = []

    for line in lines.values():
        obstacles.append((line["start"], line["end"]))

    if avoidance_lines:
        obstacles.extend(avoidance_lines)

    return obstacles


def marker_uses_auto_place(marker: dict) -> bool:
    if "auto_place" in marker:
        return bool(marker["auto_place"])

    return marker.get("type") == "thickness_triangle"


def get_best_marker_geometry(
    marker: dict,
    parameters: dict[str, float],
    template: dict,
    lines: dict[str, dict[str, Point]],
    avoidance_lines: list[Segment] | None = None
) -> tuple[Point, Point, list[Segment]]:
    target_name = marker["target"]
    line = lines[target_name]
    start = line["start"]
    end = line["end"]

    line_vector = get_vector(start, end)
    line_direction = normalize(line_vector)
    target_segment = (start, end)

    if marker_uses_auto_place(marker):
        side_direction = choose_side_direction_for_marker(
            marker=marker,
            template=template,
            lines=lines,
            start=start,
            end=end
        )
    else:
        side_direction = get_manual_side_direction(
            marker=marker,
            start=start,
            end=end
        )

    offset = resolve_value(marker.get("offset", 2), parameters)
    height = resolve_value(marker.get("height", 12), parameters)
    depth = resolve_value(marker.get("depth", 10), parameters)

    obstacles = get_marker_obstacles(
        lines=lines,
        avoidance_lines=avoidance_lines
    )

    if not marker_uses_auto_place(marker):
        position_value = get_marker_position_value(
            marker=marker,
            parameters=parameters
        )

        tip, segments = get_marker_candidate_segments(
            start=start,
            line_vector=line_vector,
            line_direction=line_direction,
            side_direction=side_direction,
            position_value=position_value,
            offset=offset,
            height=height,
            depth=depth
        )

        return tip, side_direction, segments

    candidate_positions = marker.get("candidate_positions", AUTO_MARKER_POSITIONS)

    best_tip: Point | None = None
    best_segments: list[Segment] | None = None
    best_score: float | None = None

    for raw_position in candidate_positions:
        position_value = resolve_value(raw_position, parameters)
        position_value = max(0.05, min(0.95, position_value))

        tip, segments = get_marker_candidate_segments(
            start=start,
            line_vector=line_vector,
            line_direction=line_direction,
            side_direction=side_direction,
            position_value=position_value,
            offset=offset,
            height=height,
            depth=depth
        )

        score = score_marker_candidate(
            marker_segments=segments,
            target_segment=target_segment,
            obstacles=obstacles,
            position_value=position_value
        )

        if best_score is None or score < best_score:
            best_score = score
            best_tip = tip
            best_segments = segments

    if best_tip is None or best_segments is None:
        best_tip, best_segments = get_marker_candidate_segments(
            start=start,
            line_vector=line_vector,
            line_direction=line_direction,
            side_direction=side_direction,
            position_value=0.5,
            offset=offset,
            height=height,
            depth=depth
        )

    return best_tip, side_direction, best_segments


def get_marker_segments(
    marker: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    template: dict | None = None,
    avoidance_lines: list[Segment] | None = None
) -> list[Segment]:
    target_name = marker["target"]

    if template is None:
        line = lines[target_name]
        start = line["start"]
        end = line["end"]
        line_vector = get_vector(start, end)
        line_direction = normalize(line_vector)

        position_value = get_marker_position_value(
            marker=marker,
            parameters=parameters
        )

        side_direction = get_manual_side_direction(
            marker=marker,
            start=start,
            end=end
        )

        offset = resolve_value(marker.get("offset", 2), parameters)
        height = resolve_value(marker.get("height", 12), parameters)
        depth = resolve_value(marker.get("depth", 10), parameters)

        _, segments = get_marker_candidate_segments(
            start=start,
            line_vector=line_vector,
            line_direction=line_direction,
            side_direction=side_direction,
            position_value=position_value,
            offset=offset,
            height=height,
            depth=depth
        )

        return segments

    _, _, segments = get_best_marker_geometry(
        marker=marker,
        parameters=parameters,
        template=template,
        lines=lines,
        avoidance_lines=avoidance_lines
    )

    return segments


def draw_markers(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]],
    avoidance_lines: list[Segment] | None = None
):
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
        line_direction = normalize(get_vector(start, end))

        tip, side_direction, _ = get_best_marker_geometry(
            marker=marker,
            parameters=parameters,
            template=template,
            lines=lines,
            avoidance_lines=avoidance_lines
        )

        height = resolve_value(marker.get("height", 12), parameters)
        depth = resolve_value(marker.get("depth", 10), parameters)

        add_triangle_marker(
            msp=msp,
            tip=tip,
            line_direction=line_direction,
            side_direction=side_direction,
            height=height,
            depth=depth
        )
