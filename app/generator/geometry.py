import math

from .types import Point, Segment


def get_vector(start: Point, end: Point) -> Point:
    return end[0] - start[0], end[1] - start[1]


def get_distance(start: Point, end: Point) -> float:
    dx, dy = get_vector(start, end)
    return math.sqrt(dx * dx + dy * dy)


def normalize(vector: Point) -> Point:
    x, y = vector
    length = math.sqrt(x * x + y * y)
    if length == 0:
        raise ValueError("Zero length vector")
    return x / length, y / length


def rotate_clockwise(vector: Point) -> Point:
    x, y = vector
    return y, -x


def rotate_counterclockwise(vector: Point) -> Point:
    x, y = vector
    return -y, x


def rotate_vector(vector: Point, angle_radians: float) -> Point:
    cos_a = math.cos(angle_radians)
    sin_a = math.sin(angle_radians)
    return vector[0] * cos_a - vector[1] * sin_a, vector[0] * sin_a + vector[1] * cos_a


def get_left_normal(start: Point, end: Point) -> Point:
    return rotate_counterclockwise(normalize(get_vector(start, end)))


def get_right_normal(start: Point, end: Point) -> Point:
    return rotate_clockwise(normalize(get_vector(start, end)))


def offset_point(point: Point, normal: Point, distance: float) -> Point:
    return point[0] + normal[0] * distance, point[1] + normal[1] * distance


def add_vectors(*vectors: Point) -> Point:
    return sum(vector[0] for vector in vectors), sum(vector[1] for vector in vectors)


def scale_vector(vector: Point, factor: float) -> Point:
    return vector[0] * factor, vector[1] * factor


def get_angle_degrees(start: Point, end: Point) -> float:
    dx, dy = get_vector(start, end)
    return math.degrees(math.atan2(dy, dx))


def get_arc_segments(center: Point, radius: float, start_angle: float, end_angle: float, steps: int = 16) -> list[Segment]:
    if steps < 1:
        steps = 1

    points: list[Point] = []
    for step in range(steps + 1):
        angle = math.radians(start_angle + (end_angle - start_angle) * step / steps)
        points.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))

    return list(zip(points[:-1], points[1:]))


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
