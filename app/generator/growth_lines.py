from math import cos, radians, sin

from .formulas import resolve_value
from .geometry import get_vector, normalize
from .settings import get_dimension_attribs
from .types import Point


def get_line_length(start: Point, end: Point) -> float:
    vector = get_vector(start, end)
    return (vector[0] ** 2 + vector[1] ** 2) ** 0.5


def get_point_on_line(
    line: dict[str, Point],
    point_name: str,
    parameters: dict[str, float]
) -> Point:
    start = line["start"]
    end = line["end"]

    if point_name == "start":
        return start

    if point_name == "end":
        return end

    if point_name == "middle":
        return (
            (start[0] + end[0]) / 2,
            (start[1] + end[1]) / 2
        )

    position = resolve_value(point_name, parameters)

    return (
        start[0] + (end[0] - start[0]) * position,
        start[1] + (end[1] - start[1]) * position
    )


def get_growth_direction(
    growth_line: dict,
    source_line: dict[str, Point],
    parameters: dict[str, float]
) -> Point:
    direction_type = growth_line.get("direction", "same")

    source_start = source_line["start"]
    source_end = source_line["end"]

    if direction_type == "same":
        return normalize(get_vector(source_start, source_end))

    if direction_type == "reverse":
        direction = normalize(get_vector(source_start, source_end))
        return -direction[0], -direction[1]

    if direction_type == "angle":
        angle = resolve_value(growth_line["angle"], parameters)
        return cos(radians(angle)), sin(radians(angle))

    raise ValueError(f"Unknown growth line direction: {direction_type}")


def get_growth_length(
    growth_line: dict,
    source_line: dict[str, Point],
    parameters: dict[str, float]
) -> float:
    length = growth_line.get("length", "same")

    if length == "same":
        return get_line_length(source_line["start"], source_line["end"])

    return resolve_value(length, parameters)


def get_growth_line_points(
    growth_line: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
) -> tuple[Point, Point]:
    source_name = growth_line["source"]

    if source_name not in lines:
        raise ValueError(f"Growth line source not found: {source_name}")

    source_line = lines[source_name]

    start = get_point_on_line(
        line=source_line,
        point_name=growth_line.get("from", "end"),
        parameters=parameters
    )

    direction = get_growth_direction(
        growth_line=growth_line,
        source_line=source_line,
        parameters=parameters
    )

    length = get_growth_length(
        growth_line=growth_line,
        source_line=source_line,
        parameters=parameters
    )

    end = (
        start[0] + direction[0] * length,
        start[1] + direction[1] * length
    )

    return start, end


def build_growth_lines(
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
) -> dict[str, dict[str, Point]]:
    result: dict[str, dict[str, Point]] = {}

    for growth_line in template.get("growth_lines", []):
        name = growth_line["name"]

        start, end = get_growth_line_points(
            growth_line=growth_line,
            parameters=parameters,
            lines=lines
        )

        result[name] = {
            "start": start,
            "end": end
        }

    return result


def draw_growth_lines(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, Point]]
):
    growth_lines = build_growth_lines(
        template=template,
        parameters=parameters,
        lines=lines
    )

    for line in growth_lines.values():
        msp.add_line(
            line["start"],
            line["end"],
            dxfattribs=get_dimension_attribs()
        )
