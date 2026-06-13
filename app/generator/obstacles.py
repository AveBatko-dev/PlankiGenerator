from .angles import get_angle_mark_segments
from .dimensions import get_parallel_dimension_segments
from .formulas import resolve_point
from .hooks import get_single_hook_geometry, get_single_hook_segments
from .markers import get_marker_segments
from .types import Point, Segment


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
            obstacles.extend(get_parallel_dimension_segments(dim=dim, parameters=parameters, lines=lines, template=template))

    for marker in template.get("markers", []):
        marker_type = marker.get("type")
        if marker_type in ("triangle", "thickness_triangle"):
            obstacles.extend(get_marker_segments(marker=marker, parameters=parameters, lines=lines))

    for mark in template.get("angle_marks", []):
        if mark.get("enabled", False):
            obstacles.extend(get_angle_mark_segments(mark=mark, parameters=parameters, lines=lines, template=template))

    return obstacles
