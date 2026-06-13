from config import CAD_STYLES

from .drawing import add_rounded_profile_path, add_text
from .formulas import resolve_point, resolve_value
from .geometry import get_left_normal, get_right_normal, get_vector, normalize
from .settings import get_main_profile_width
from .types import Point


def add_point_unique(points: list[tuple[float, float, float]], point: tuple[float, float, float]):
    if not points:
        points.append(point)
        return

    last_x, last_y, _ = points[-1]
    x, y, _ = point

    if abs(last_x - x) < 0.0001 and abs(last_y - y) < 0.0001:
        return

    points.append(point)


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


def build_line(element: dict, parameters: dict[str, float]) -> dict[str, Point]:
    return {
        "start": resolve_point(element["start"], parameters),
        "end": resolve_point(element["end"], parameters)
    }


def build_named_lines(template: dict, parameters: dict[str, float]) -> dict[str, dict[str, Point]]:
    profile = template["profile"]
    if profile.get("type") != "connected_path":
        raise ValueError("Only profile.type='connected_path' is supported")

    lines = {}

    for element in profile["elements"]:
        if element["type"] != "line":
            raise ValueError(f"Unsupported profile element type: {element['type']}")

        lines[element["name"]] = build_line(element=element, parameters=parameters)

    for element in template.get("reference_lines", []):
        if element["type"] != "line":
            raise ValueError(f"Unsupported reference line type: {element['type']}")

        lines[element["name"]] = build_line(element=element, parameters=parameters)

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
    profile_width = get_main_profile_width(template=template)
    points = build_profile_path(lines, template)
    add_rounded_profile_path(msp=msp, points=points, width=profile_width)

    for element in template["profile"]["elements"]:
        line = lines[element["name"]]
        add_profile_line_label(msp=msp, element=element, start=line["start"], end=line["end"], parameters=parameters)
