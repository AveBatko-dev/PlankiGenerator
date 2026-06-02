from .drawing import add_text, estimate_text_size
from .geometry import get_distance, normalize
from .types import Point, Segment

Box = tuple[float, float, float, float]
LABEL_LINEWEIGHT = 40


def get_label_text_position(anchor: Point, direction: Point, text_width: float, text_height: float) -> Point:
    direction = normalize(direction)
    x, y = anchor

    if direction[0] < -0.15:
        x -= text_width
    elif abs(direction[0]) <= 0.15:
        x -= text_width / 2

    if direction[1] < -0.15:
        y -= text_height
    elif abs(direction[1]) <= 0.15:
        y -= text_height / 2

    return x, y


def get_label_box(position: Point, text_width: float, text_height: float) -> Box:
    x, y = position
    return x, y, x + text_width, y + text_height


def get_box_segments(box: Box) -> list[Segment]:
    min_x, min_y, max_x, max_y = box
    return [
        ((min_x, min_y), (max_x, min_y)),
        ((max_x, min_y), (max_x, max_y)),
        ((max_x, max_y), (min_x, max_y)),
        ((min_x, max_y), (min_x, min_y)),
    ]


def point_in_box(point: Point, box: Box) -> bool:
    min_x, min_y, max_x, max_y = box
    return min_x <= point[0] <= max_x and min_y <= point[1] <= max_y


def orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(first: Segment, second: Segment) -> bool:
    a, b = first
    c, d = second
    return orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0


def segment_intersects_box(segment: Segment, box: Box) -> bool:
    start, end = segment
    if point_in_box(start, box) or point_in_box(end, box):
        return True
    return any(segments_intersect(segment, edge) for edge in get_box_segments(box))


def point_to_segment_distance(point: Point, segment: Segment) -> float:
    start, end = segment
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy

    if length_squared == 0:
        return get_distance(point, start)

    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    projection = (start[0] + dx * t, start[1] + dy * t)
    return get_distance(point, projection)


def box_center(box: Box) -> Point:
    min_x, min_y, max_x, max_y = box
    return (min_x + max_x) / 2, (min_y + max_y) / 2


def box_to_segment_distance(box: Box, segment: Segment) -> float:
    center = box_center(box)
    points = [center, (box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    return min(point_to_segment_distance(point, segment) for point in points)


def score_label_box(box: Box, anchor: Point, obstacles: list[Segment], candidate_index: int) -> float:
    score = get_distance(anchor, box_center(box)) * 2 + candidate_index * 20

    for obstacle in obstacles:
        if segment_intersects_box(obstacle, box):
            score += 10000
            continue

        distance = box_to_segment_distance(box, obstacle)
        if distance < 2:
            score += (2 - distance) * 600
        elif distance < 6:
            score += (6 - distance) * 60

    return score


def unique_directions(directions: list[Point]) -> list[Point]:
    result: list[Point] = []
    seen: set[tuple[int, int]] = set()

    for direction in directions:
        try:
            normalized = normalize(direction)
        except ValueError:
            continue

        key = (round(normalized[0] * 1000), round(normalized[1] * 1000))
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)

    return result


def choose_label_position(
    anchor: Point,
    preferred_directions: list[Point],
    gap: float,
    text_width: float,
    text_height: float,
    obstacles: list[Segment] | None = None,
) -> Point:
    directions = unique_directions(preferred_directions)
    obstacle_segments = obstacles or []
    best_position: Point | None = None
    best_score: float | None = None
    candidate_index = 0

    for distance_multiplier in (1.0, 1.35, 1.75):
        distance = gap * distance_multiplier
        for direction in directions:
            candidate_anchor = (anchor[0] + direction[0] * distance, anchor[1] + direction[1] * distance)
            position = get_label_text_position(candidate_anchor, direction, text_width, text_height)
            box = get_label_box(position, text_width, text_height)
            score = score_label_box(box, anchor, obstacle_segments, candidate_index)
            candidate_index += 1

            if best_score is None or score < best_score:
                best_score = score
                best_position = position

    return best_position if best_position is not None else anchor


def draw_auto_label(
    msp,
    text: str,
    anchor: Point,
    preferred_directions: list[Point],
    gap: float,
    obstacles: list[Segment] | None = None,
    height: float = 2.5,
    rotation: float = 0,
    lineweight: int = LABEL_LINEWEIGHT,
):
    text_width, text_height = estimate_text_size(text=text, height=height)
    position = choose_label_position(
        anchor=anchor,
        preferred_directions=preferred_directions,
        gap=gap,
        text_width=text_width,
        text_height=text_height,
        obstacles=obstacles,
    )
    add_text(msp=msp, text=text, position=position, height=height, rotation=rotation, lineweight=lineweight)
