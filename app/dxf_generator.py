from pathlib import Path
from typing import Any
import math

import ezdxf

from config import CAD_STYLES


PROFILE_LAYER = CAD_STYLES["profile"]["layer"]
DIM_LAYER = CAD_STYLES["dimensions"]["layer"]
TEXT_LAYER = CAD_STYLES["text"]["layer"]

Point = tuple[float, float]
Segment = tuple[Point, Point]
Rect = tuple[float, float, float, float]


def fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(round(value, 2))


def resolve_value(value: Any, parameters: dict[str, float]) -> float:
    if isinstance(value, str):
        safe_locals = {key: float(val) for key, val in parameters.items()}
        safe_locals.update(
            {
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "radians": math.radians,
                "degrees": math.degrees,
                "pi": math.pi,
            }
        )

        try:
            return float(eval(value, {"__builtins__": {}}, safe_locals))
        except NameError:
            raise ValueError(f"Missing parameter in expression: {value}")
        except Exception as error:
            raise ValueError(f"Invalid expression: {value}. {error}")

    return float(value)


def resolve_point(point: list[Any], parameters: dict[str, float]) -> Point:
    return resolve_value(point[0], parameters), resolve_value(point[1], parameters)


def get_template_default(template: dict, name: str, fallback: float) -> float:
    return float(template.get("defaults", {}).get(name, fallback))


def setup_document():
    doc = ezdxf.new("R2010")

    for style in CAD_STYLES.values():
        layer_name = style["layer"]

        if layer_name not in doc.layers:
            doc.layers.new(layer_name)

        layer = doc.layers.get(layer_name)
        layer.dxf.color = style["color"]
        layer.dxf.lineweight = style["lineweight"]

    return doc


def add_text(msp, text: str, position: Point, height: float | None = None, rotation: float = 0):
    if height is None:
        height = CAD_STYLES["text"]["height"]

    msp.add_text(
        text,
        dxfattribs={
            "height": height,
            "rotation": rotation,
            "layer": TEXT_LAYER,
            "color": CAD_STYLES["text"]["color"],
            "lineweight": CAD_STYLES["text"]["lineweight"],
        },
    ).set_placement(position)


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


def get_left_normal(start: Point, end: Point) -> Point:
    dx, dy = normalize(get_vector(start, end))
    return -dy, dx


def get_right_normal(start: Point, end: Point) -> Point:
    dx, dy = normalize(get_vector(start, end))
    return dy, -dx


def offset_point(point: Point, normal: Point, distance: float) -> Point:
    return point[0] + normal[0] * distance, point[1] + normal[1] * distance


def add_vectors(*vectors: Point) -> Point:
    return sum(vector[0] for vector in vectors), sum(vector[1] for vector in vectors)


def scale_vector(vector: Point, factor: float) -> Point:
    return vector[0] * factor, vector[1] * factor


def get_angle_degrees(start: Point, end: Point) -> float:
    dx, dy = get_vector(start, end)
    return math.degrees(math.atan2(dy, dx))


def distance_point_to_segment(point: Point, start: Point, end: Point) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    abx = bx - ax
    aby = by - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return math.sqrt((px - ax) ** 2 + (py - ay) ** 2)

    t = ((px - ax) * abx + (py - ay) * aby) / ab_len_sq
    t = max(0, min(1, t))
    closest = (ax + abx * t, ay + aby * t)
    return math.sqrt((px - closest[0]) ** 2 + (py - closest[1]) ** 2)


def push_point_away_from_lines(
    point: Point,
    move_direction: Point,
    lines: list[Segment],
    min_clearance: float,
    step: float = 4,
    max_iterations: int = 20,
) -> Point:
    result = point
    direction = normalize(move_direction)

    for _ in range(max_iterations):
        if all(distance_point_to_segment(result, start, end) >= min_clearance for start, end in lines):
            return result

        result = (result[0] + direction[0] * step, result[1] + direction[1] * step)

    return result


def estimate_text_size(text: str, height: float) -> tuple[float, float]:
    return max(height * 0.65 * len(text), height * 0.65), height


def rotate_point(point: Point, origin: Point, angle_degrees: float) -> Point:
    angle = math.radians(angle_degrees)
    x, y = point[0] - origin[0], point[1] - origin[1]
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return origin[0] + x * cos_a - y * sin_a, origin[1] + x * sin_a + y * cos_a


def get_text_rect(text: str, position: Point, height: float, rotation: float = 0) -> Rect:
    width, text_height = estimate_text_size(text=text, height=height)
    x, y = position
    corners = [(x, y), (x + width, y), (x + width, y + text_height), (x, y + text_height)]

    if rotation:
        corners = [rotate_point(corner, position, rotation) for corner in corners]

    xs = [corner[0] for corner in corners]
    ys = [corner[1] for corner in corners]
    return min(xs), min(ys), max(xs), max(ys)


def get_rect_corners(rect: Rect) -> list[Point]:
    min_x, min_y, max_x, max_y = rect
    return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]


def get_rect_edges(rect: Rect) -> list[Segment]:
    corners = get_rect_corners(rect)
    return [(corners[0], corners[1]), (corners[1], corners[2]), (corners[2], corners[3]), (corners[3], corners[0])]


def point_in_rect(point: Point, rect: Rect) -> bool:
    min_x, min_y, max_x, max_y = rect
    return min_x <= point[0] <= max_x and min_y <= point[1] <= max_y


def orientation(a: Point, b: Point, c: Point) -> float:
    return (b[1] - a[1]) * (c[0] - b[0]) - (b[0] - a[0]) * (c[1] - b[1])


def point_on_segment(point: Point, start: Point, end: Point) -> bool:
    return (
        min(start[0], end[0]) - 0.0001 <= point[0] <= max(start[0], end[0]) + 0.0001
        and min(start[1], end[1]) - 0.0001 <= point[1] <= max(start[1], end[1]) + 0.0001
        and abs(orientation(start, end, point)) < 0.0001
    )


def segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True

    return (
        point_on_segment(b1, a1, a2)
        or point_on_segment(b2, a1, a2)
        or point_on_segment(a1, b1, b2)
        or point_on_segment(a2, b1, b2)
    )


def distance_point_to_rect(point: Point, rect: Rect) -> float:
    if point_in_rect(point, rect):
        return 0

    min_x, min_y, max_x, max_y = rect
    dx = max(min_x - point[0], 0, point[0] - max_x)
    dy = max(min_y - point[1], 0, point[1] - max_y)
    return math.sqrt(dx * dx + dy * dy)


def distance_rect_to_segment(rect: Rect, start: Point, end: Point) -> float:
    if point_in_rect(start, rect) or point_in_rect(end, rect):
        return 0

    if any(segments_intersect(start, end, edge_start, edge_end) for edge_start, edge_end in get_rect_edges(rect)):
        return 0

    corner_distances = [distance_point_to_segment(corner, start, end) for corner in get_rect_corners(rect)]
    endpoint_distances = [distance_point_to_rect(start, rect), distance_point_to_rect(end, rect)]
    return min(corner_distances + endpoint_distances)


def get_min_rect_clearance(rect: Rect, obstacles: list[Segment]) -> float:
    if not obstacles:
        return float("inf")

    return min(distance_rect_to_segment(rect, start, end) for start, end in obstacles)


def get_text_center(position: Point, text: str, height: float) -> Point:
    width, text_height = estimate_text_size(text=text, height=height)
    return position[0] + width / 2, position[1] + text_height / 2


def get_text_position_from_center(center: Point, text: str, height: float) -> Point:
    width, text_height = estimate_text_size(text=text, height=height)
    return center[0] - width / 2, center[1] - text_height / 2


def iter_label_candidate_positions(
    anchor: Point,
    text: str,
    height: float,
    side_direction: Point,
    body_direction: Point,
    min_clearance: float,
):
    width, text_height = estimate_text_size(text=text, height=height)
    direction_pairs = [(1, 1), (1, 0), (0, 1), (1, -1), (-1, 1), (0, -1), (-1, 0), (-1, -1)]
    extras = [0, 4, 8, 12, 16, 24, 32, 48]
    candidates: list[tuple[float, int, Point]] = []

    for direction_priority, (side_sign, body_sign) in enumerate(direction_pairs):
        side_extras = extras if side_sign else [0]
        body_extras = extras if body_sign else [0]

        for side_extra in side_extras:
            for body_extra in body_extras:
                center = anchor

                if side_sign:
                    side_distance = min_clearance + side_extra + width / 2
                    center = add_vectors(center, scale_vector(side_direction, side_sign * side_distance))

                if body_sign:
                    body_distance = min_clearance + body_extra + text_height / 2
                    center = add_vectors(center, scale_vector(body_direction, body_sign * body_distance))

                position = get_text_position_from_center(center=center, text=text, height=height)
                score = side_extra + body_extra + direction_priority * 0.01 + get_distance(anchor, center) * 0.001
                candidates.append((score, direction_priority, position))

    yielded: set[tuple[int, int]] = set()
    for _, _, position in sorted(candidates, key=lambda item: (item[0], item[1])):
        key = (round(position[0] * 1000), round(position[1] * 1000))
        if key in yielded:
            continue
        yielded.add(key)
        yield position


def choose_auto_label_position(
    text: str,
    anchor: Point,
    side_direction: Point,
    body_direction: Point,
    height: float,
    rotation: float,
    obstacles: list[Segment],
    min_clearance: float,
) -> Point:
    fallback_position: Point | None = None
    fallback_clearance = -1.0
    fallback_distance = float("inf")

    for position in iter_label_candidate_positions(
        anchor=anchor,
        text=text,
        height=height,
        side_direction=side_direction,
        body_direction=body_direction,
        min_clearance=min_clearance,
    ):
        rect = get_text_rect(text=text, position=position, height=height, rotation=rotation)
        clearance = get_min_rect_clearance(rect=rect, obstacles=obstacles)
        center = get_text_center(position=position, text=text, height=height)
        anchor_distance = get_distance(anchor, center)

        if clearance >= min_clearance:
            return position

        if clearance > fallback_clearance or (clearance == fallback_clearance and anchor_distance < fallback_distance):
            fallback_position = position
            fallback_clearance = clearance
            fallback_distance = anchor_distance

    if fallback_position is not None:
        return fallback_position

    return anchor


def add_profile_path(msp, points: list[tuple[float, float, float]], width: float):
    msp.add_lwpolyline(
        points,
        format="xyb",
        dxfattribs={
            "layer": PROFILE_LAYER,
            "color": CAD_STYLES["profile"]["color"],
            "lineweight": CAD_STYLES["profile"]["lineweight"],
            "const_width": width,
        },
    )


def add_point_unique(points: list[tuple[float, float, float]], point: tuple[float, float, float]):
    if not points:
        points.append(point)
        return

    last_x, last_y, _ = points[-1]
    x, y, _ = point

    if abs(last_x - x) < 0.0001 and abs(last_y - y) < 0.0001:
        return

    points.append(point)


def get_tick_segment(position: Point, direction: Point, size: float = 6) -> Segment:
    x, y = position
    dx, dy = normalize(direction)
    angle = math.radians(45)
    tick_dx = dx * math.cos(angle) - dy * math.sin(angle)
    tick_dy = dx * math.sin(angle) + dy * math.cos(angle)
    half = size / 2
    return (x - tick_dx * half, y - tick_dy * half), (x + tick_dx * half, y + tick_dy * half)


def add_tick(msp, position: Point, direction: Point, size: float = 6):
    start, end = get_tick_segment(position=position, direction=direction, size=size)

    msp.add_line(
        start,
        end,
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )


def get_angle_tick_segment(center: Point, radius: float, angle_degrees: float, size: float = 15) -> Segment:
    angle = math.radians(angle_degrees)
    point = (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)
    tangent = (-math.sin(angle), math.cos(angle))
    tx, ty = normalize(tangent)
    tick_angle = math.radians(45)
    tick_dx = tx * math.cos(tick_angle) - ty * math.sin(tick_angle)
    tick_dy = tx * math.sin(tick_angle) + ty * math.cos(tick_angle)
    half = size / 2
    return (point[0] - tick_dx * half, point[1] - tick_dy * half), (point[0] + tick_dx * half, point[1] + tick_dy * half)


def add_angle_tick(msp, center: Point, radius: float, angle_degrees: float, size: float = 15):
    start, end = get_angle_tick_segment(center=center, radius=radius, angle_degrees=angle_degrees, size=size)

    msp.add_line(
        start,
        end,
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )


def add_hook_label(
    msp,
    text: str,
    base: Point,
    hook_tip: Point,
    hook_direction: Point,
    line_direction: Point,
    side_direction: Point,
    position: str,
    hook: dict,
    avoidance_lines: list[Segment] | None = None,
):
    height = float(hook.get("label_height", CAD_STYLES["text"]["height"]))
    rotation = float(hook.get("label_rotation", 0))

    if hook.get("label_auto_place", False):
        label_anchor = hook.get("label_anchor", "base")
        if label_anchor == "hook_tip":
            anchor = hook_tip
        elif label_anchor == "base":
            anchor = base
        else:
            raise ValueError(f"Unknown hook label anchor: {label_anchor}")

        if position == "start":
            body_direction = line_direction
        elif position == "end":
            body_direction = (-line_direction[0], -line_direction[1])
        else:
            raise ValueError(f"Unknown hook label position: {position}")

        label_position = choose_auto_label_position(
            text=text,
            anchor=anchor,
            side_direction=side_direction,
            body_direction=body_direction,
            height=height,
            rotation=rotation,
            obstacles=avoidance_lines or [],
            min_clearance=float(hook.get("label_min_clearance", 8)),
        )
    else:
        label_anchor = hook.get("label_anchor", "base")
        label_side_offset = float(hook.get("label_side_offset", 16))

        if label_anchor == "hook_tip":
            label_forward_offset = float(hook.get("label_forward_offset", 0))
            label_position = (
                hook_tip[0] + hook_direction[0] * label_side_offset + line_direction[0] * label_forward_offset,
                hook_tip[1] + hook_direction[1] * label_side_offset + line_direction[1] * label_forward_offset,
            )

            if hook.get("label_avoid_profile", True) and avoidance_lines:
                label_position = push_point_away_from_lines(
                    point=label_position,
                    move_direction=hook_direction,
                    lines=avoidance_lines,
                    min_clearance=float(hook.get("label_min_clearance", 18)),
                    step=float(hook.get("label_avoid_step", 4)),
                    max_iterations=int(hook.get("label_avoid_max_iterations", 20)),
                )

        elif label_anchor == "base":
            label_back_offset = float(hook.get("label_back_offset", 18))

            if position == "start":
                label_position = (
                    base[0] - line_direction[0] * label_back_offset + side_direction[0] * label_side_offset,
                    base[1] - line_direction[1] * label_back_offset + side_direction[1] * label_side_offset,
                )
            elif position == "end":
                label_position = (
                    base[0] + line_direction[0] * label_back_offset + side_direction[0] * label_side_offset,
                    base[1] + line_direction[1] * label_back_offset + side_direction[1] * label_side_offset,
                )
            else:
                raise ValueError(f"Unknown hook label position: {position}")
        else:
            raise ValueError(f"Unknown hook label anchor: {label_anchor}")

    add_text(msp=msp, text=text, position=label_position, height=height, rotation=rotation)


def add_profile_line_label(msp, element: dict, start: Point, end: Point, parameters: dict[str, float]):
    label = element.get("label")
    if not label:
        return

    line_vector = get_vector(start, end)
    line_direction = normalize(line_vector)

    position = element.get("label_position", "middle")
    if position == "start":
        position_value = 0
    elif position == "end":
        position_value = 1
    elif position == "middle":
        position_value = 0.5
    else:
        position_value = resolve_value(position, parameters)

    base = (start[0] + line_vector[0] * position_value, start[1] + line_vector[1] * position_value)

    side = element.get("label_side", "left")
    if side == "left":
        side_direction = get_left_normal(start, end)
    elif side == "right":
        side_direction = get_right_normal(start, end)
    else:
        raise ValueError(f"Unknown profile line label side: {side}")

    along_offset = resolve_value(element.get("label_along_offset", 0), parameters)
    side_offset = resolve_value(element.get("label_side_offset", 12), parameters)

    label_position = (
        base[0] + line_direction[0] * along_offset + side_direction[0] * side_offset,
        base[1] + line_direction[1] * along_offset + side_direction[1] * side_offset,
    )

    add_text(
        msp=msp,
        text=label,
        position=label_position,
        height=element.get("label_height", CAD_STYLES["text"]["height"]),
        rotation=element.get("label_rotation", 0),
    )


def build_named_lines(template: dict, parameters: dict[str, float]) -> dict[str, dict[str, Point]]:
    profile = template["profile"]
    if profile.get("type") != "connected_path":
        raise ValueError("Only profile.type='connected_path' is supported")

    lines = {}
    for element in profile["elements"]:
        if element["type"] != "line":
            raise ValueError(f"Unsupported profile element type: {element['type']}")

        name = element["name"]
        lines[name] = {"start": resolve_point(element["start"], parameters), "end": resolve_point(element["end"], parameters)}

    return lines


def build_profile_path(lines: dict[str, dict[str, Point]], template: dict) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []

    for element in template["profile"]["elements"]:
        line = lines[element["name"]]
        start = line["start"]
        end = line["end"]
        add_point_unique(points, (start[0], start[1], 0))
        add_point_unique(points, (end[0], end[1], 0))

    return points


def draw_profile(msp, template: dict, lines: dict[str, dict[str, Point]], parameters: dict[str, float]):
    profile_width = get_template_default(template=template, name="profile_width", fallback=CAD_STYLES["profile"]["width"])

    points = build_profile_path(lines, template)
    add_profile_path(msp=msp, points=points, width=profile_width)

    for element in template["profile"]["elements"]:
        line = lines[element["name"]]
        add_profile_line_label(msp=msp, element=element, start=line["start"], end=line["end"], parameters=parameters)


def get_parallel_dimension_segments(dim: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]) -> list[Segment]:
    target_name = dim["target"]
    line = lines[target_name]
    p1 = line["start"]
    p2 = line["end"]
    offset = resolve_value(dim.get("offset", 22), parameters)
    side = dim.get("side", "left")

    if side == "left":
        normal = get_left_normal(p1, p2)
    elif side == "right":
        normal = get_right_normal(p1, p2)
    else:
        raise ValueError(f"Unknown dimension side: {side}")

    d1 = offset_point(p1, normal, offset)
    d2 = offset_point(p2, normal, offset)
    profile_gap = CAD_STYLES["profile"]["width"] * 2
    dimension_direction = get_vector(d1, d2)

    return [
        (d1, d2),
        (offset_point(p1, normal, profile_gap), d1),
        (offset_point(p2, normal, profile_gap), d2),
        get_tick_segment(d1, direction=dimension_direction, size=15),
        get_tick_segment(d2, direction=dimension_direction, size=15),
    ]


def draw_parallel_dimension(msp, dim: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    param_name = dim["param"]
    if param_name not in parameters:
        raise ValueError(f"Missing dimension parameter: {param_name}")

    target_name = dim["target"]
    if target_name not in lines:
        raise ValueError(f"Dimension target line not found: {target_name}")

    line = lines[target_name]
    p1 = line["start"]
    p2 = line["end"]
    offset = resolve_value(dim.get("offset", 22), parameters)
    side = dim.get("side", "left")

    if side == "left":
        normal = get_left_normal(p1, p2)
    elif side == "right":
        normal = get_right_normal(p1, p2)
    else:
        raise ValueError(f"Unknown dimension side: {side}")

    d1 = offset_point(p1, normal, offset)
    d2 = offset_point(p2, normal, offset)
    attribs = {"layer": DIM_LAYER, "color": CAD_STYLES["dimensions"]["color"], "lineweight": CAD_STYLES["dimensions"]["lineweight"]}

    msp.add_line(d1, d2, dxfattribs=attribs)
    profile_gap = CAD_STYLES["profile"]["width"] * 2
    msp.add_line(offset_point(p1, normal, profile_gap), d1, dxfattribs=attribs)
    msp.add_line(offset_point(p2, normal, profile_gap), d2, dxfattribs=attribs)

    dimension_direction = get_vector(d1, d2)
    add_tick(msp, d1, direction=dimension_direction, size=15)
    add_tick(msp, d2, direction=dimension_direction, size=15)

    mid = ((d1[0] + d2[0]) / 2, (d1[1] + d2[1]) / 2)
    text_position = offset_point(mid, normal, 12)

    if dim.get("text_rotation") == "auto":
        text_rotation = get_angle_degrees(d1, d2)
    else:
        text_rotation = dim.get("text_rotation", 0)

    add_text(msp=msp, text=fmt(parameters[param_name]), position=text_position, height=dim.get("text_height", CAD_STYLES["text"]["height"]), rotation=text_rotation)


def rotate_clockwise(vector: Point) -> Point:
    x, y = vector
    return y, -x


def rotate_counterclockwise(vector: Point) -> Point:
    x, y = vector
    return -y, x


def get_single_hook_geometry(hook: dict, lines: dict[str, dict[str, Point]], template: dict) -> dict[str, Any]:
    attach_to = hook["attach_to"]
    position = hook["position"]

    if attach_to not in lines:
        raise ValueError(f"Hook target line not found: {attach_to}")

    line = lines[attach_to]
    line_start = line["start"]
    line_end = line["end"]
    width = get_template_default(template=template, name="profile_width", fallback=CAD_STYLES["profile"]["width"])
    length = float(hook["length"])
    angle = float(hook.get("angle", 90))

    if angle != 90:
        raise ValueError("Only 90 degree hooks are supported for now")

    line_direction = normalize(get_vector(line_start, line_end))
    radius = length / 2
    join_overlap = width * 1.6
    inner_join_overlap = width * 0.28

    if position == "start":
        base = line_start
        side = hook.get("side", "right")

        if side == "right":
            side_direction = rotate_clockwise(line_direction)
            bulge = 0.4142
        elif side == "left":
            side_direction = rotate_counterclockwise(line_direction)
            bulge = -0.4142
        else:
            raise ValueError(f"Unknown hook side: {side}")

        p0 = (base[0] + line_direction[0] * join_overlap, base[1] + line_direction[1] * join_overlap)
        p1 = base
        p2 = (base[0] + side_direction[0] * radius, base[1] + side_direction[1] * radius)
        p3 = (p2[0] + line_direction[0] * length, p2[1] + line_direction[1] * length)
        inner_patch_start = (p2[0] - line_direction[0] * inner_join_overlap, p2[1] - line_direction[1] * inner_join_overlap)

    elif position == "end":
        base = line_end
        side = hook.get("side", "right")

        if side == "right":
            side_direction = rotate_clockwise(line_direction)
            bulge = -0.4142
        elif side == "left":
            side_direction = rotate_counterclockwise(line_direction)
            bulge = 0.4142
        else:
            raise ValueError(f"Unknown hook side: {side}")

        back_direction = (-line_direction[0], -line_direction[1])
        p0 = (base[0] + back_direction[0] * join_overlap, base[1] + back_direction[1] * join_overlap)
        p1 = base
        p2 = (base[0] + side_direction[0] * radius, base[1] + side_direction[1] * radius)
        p3 = (p2[0] + back_direction[0] * length, p2[1] + back_direction[1] * length)
        inner_patch_start = (p2[0] - back_direction[0] * inner_join_overlap, p2[1] - back_direction[1] * inner_join_overlap)

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
        "bulge": bulge,
        "position": position,
    }


def get_single_hook_segments(geometry: dict[str, Any]) -> list[Segment]:
    return [(geometry["p0"], geometry["p1"]), (geometry["p1"], geometry["p2"]), (geometry["p2"], geometry["p3"]), (geometry["inner_patch_start"], geometry["inner_patch_end"])]


def draw_single_hook(msp, hook: dict, lines: dict[str, dict[str, Point]], template: dict, avoidance_lines: list[Segment] | None = None):
    geometry = get_single_hook_geometry(hook=hook, lines=lines, template=template)
    width = geometry["width"]
    points = [
        (geometry["p0"][0], geometry["p0"][1], 0),
        (geometry["p1"][0], geometry["p1"][1], geometry["bulge"]),
        (geometry["p2"][0], geometry["p2"][1], 0),
        (geometry["p3"][0], geometry["p3"][1], 0),
    ]

    add_profile_path(msp=msp, points=points, width=width)
    add_profile_path(
        msp=msp,
        points=[(geometry["inner_patch_start"][0], geometry["inner_patch_start"][1], 0), (geometry["inner_patch_end"][0], geometry["inner_patch_end"][1], 0)],
        width=width,
    )

    label = hook.get("label")
    if label:
        hook_direction = normalize(get_vector(geometry["p2"], geometry["p3"]))
        add_hook_label(
            msp=msp,
            text=label,
            base=geometry["base"],
            hook_tip=geometry["p3"],
            hook_direction=hook_direction,
            line_direction=geometry["line_direction"],
            side_direction=geometry["side_direction"],
            position=geometry["position"],
            hook=hook,
            avoidance_lines=avoidance_lines,
        )


def draw_hooks(msp, template: dict, lines: dict[str, dict[str, Point]], parameters: dict[str, float], avoidance_lines: list[Segment] | None = None):
    width = get_template_default(template=template, name="profile_width", fallback=CAD_STYLES["profile"]["width"])

    for hook in template.get("hooks", []):
        hook_type = hook.get("type")

        if hook_type == "hook":
            draw_single_hook(msp=msp, hook=hook, lines=lines, template=template, avoidance_lines=avoidance_lines)
        elif hook_type == "line":
            start = resolve_point(hook["start"], parameters)
            end = resolve_point(hook["end"], parameters)
            add_profile_path(msp=msp, points=[(start[0], start[1], 0), (end[0], end[1], 0)], width=width)
        else:
            raise ValueError(f"Unknown hook type: {hook_type}")


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
        dxfattribs={"layer": DIM_LAYER, "color": CAD_STYLES["dimensions"]["color"], "lineweight": CAD_STYLES["dimensions"]["lineweight"]},
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


def draw_dimensions(msp, template: dict, parameters: dict[str, float], lines: dict[str, dict[str, Point]]):
    for dim in template.get("dimensions", []):
        dim_type = dim.get("type")

        if dim_type == "parallel_to_line":
            draw_parallel_dimension(msp=msp, dim=dim, parameters=parameters, lines=lines)
        else:
            raise ValueError(f"Unknown dimension type: {dim_type}")


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
    center = line_1["end"]
    radius = resolve_value(mark.get("radius", 28), parameters)
    angle_1 = get_angle_degrees(center, line_1["start"])
    angle_2 = get_angle_degrees(center, line_2["end"])
    draw_angle_1 = angle_1
    draw_angle_2 = angle_2

    while draw_angle_2 < draw_angle_1:
        draw_angle_2 += 360

    if mark.get("arc_side") == "other":
        draw_angle_1, draw_angle_2 = draw_angle_2, draw_angle_1 + 360

    return center, radius, draw_angle_1, draw_angle_2


def get_arc_segments(center: Point, radius: float, start_angle: float, end_angle: float, steps: int = 16) -> list[Segment]:
    if steps < 1:
        steps = 1

    points: list[Point] = []
    for step in range(steps + 1):
        angle = math.radians(start_angle + (end_angle - start_angle) * step / steps)
        points.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))

    return list(zip(points[:-1], points[1:]))


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

        center, radius, draw_angle_1, draw_angle_2 = get_angle_mark_geometry(mark=mark, parameters=parameters, lines=lines)

        attribs = {"layer": DIM_LAYER, "color": CAD_STYLES["dimensions"]["color"], "lineweight": CAD_STYLES["dimensions"]["lineweight"]}
        msp.add_arc(center=center, radius=radius, start_angle=draw_angle_1, end_angle=draw_angle_2, dxfattribs=attribs)
        angle_tick_size = resolve_value(mark.get("tick_size", 15), parameters)
        add_angle_tick(msp=msp, center=center, radius=radius, angle_degrees=draw_angle_1, size=angle_tick_size)
        add_angle_tick(msp=msp, center=center, radius=radius, angle_degrees=draw_angle_2, size=angle_tick_size)

        mid_angle_degrees = (draw_angle_1 + draw_angle_2) / 2
        mid_angle = math.radians(mid_angle_degrees)
        text_radius = radius + resolve_value(mark.get("text_offset", 8), parameters)
        text_position = (center[0] + math.cos(mid_angle) * text_radius, center[1] + math.sin(mid_angle) * text_radius)

        add_text(
            msp=msp,
            text=f"{fmt(parameters[mark['param']])}°",
            position=text_position,
            height=mark.get("text_height", CAD_STYLES["text"]["height"]),
            rotation=mark.get("text_rotation", 0),
        )


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
            obstacles.extend(get_parallel_dimension_segments(dim=dim, parameters=parameters, lines=lines))

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
