from pathlib import Path
from typing import Any
import math

import ezdxf

from config import CAD_STYLES


PROFILE_LAYER = CAD_STYLES["profile"]["layer"]
DIM_LAYER = CAD_STYLES["dimensions"]["layer"]
TEXT_LAYER = CAD_STYLES["text"]["layer"]


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


def resolve_point(point: list[Any], parameters: dict[str, float]) -> tuple[float, float]:
    return (
        resolve_value(point[0], parameters),
        resolve_value(point[1], parameters),
    )


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


def add_text(
    msp,
    text: str,
    position: tuple[float, float],
    height: float | None = None,
    rotation: float = 0,
):
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

def add_hook_label(
    msp,
    text: str,
    base: tuple[float, float],
    line_direction: tuple[float, float],
    side_direction: tuple[float, float],
    position: str,
    hook: dict,
):
    label_back_offset = float(hook.get("label_back_offset", 18))
    label_side_offset = float(hook.get("label_side_offset", 16))

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

    add_text(
        msp=msp,
        text=text,
        position=label_position,
        height=hook.get("label_height", CAD_STYLES["text"]["height"]),
        rotation=hook.get("label_rotation", 0),
    )


def add_tick(
    msp,
    position: tuple[float, float],
    direction: tuple[float, float],
    size: float = 6,
):
    x, y = position

    dx, dy = normalize(direction)

    # Засечка должна быть повернута относительно самой размерной линии,
    # а не всегда иметь фиксированный мировой угол 45 градусов.
    angle = math.radians(45)

    tick_dx = dx * math.cos(angle) - dy * math.sin(angle)
    tick_dy = dx * math.sin(angle) + dy * math.cos(angle)

    half = size / 2

    msp.add_line(
        (x - tick_dx * half, y - tick_dy * half),
        (x + tick_dx * half, y + tick_dy * half),
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },

    )

def add_angle_tick(
    msp,
    center: tuple[float, float],
    radius: float,
    angle_degrees: float,
    size: float = 15,
):
    angle = math.radians(angle_degrees)

    point = (
        center[0] + math.cos(angle) * radius,
        center[1] + math.sin(angle) * radius,
    )

    # Локальное направление дуги в точке — касательная.
    tangent = (
        -math.sin(angle),
        math.cos(angle),
    )

    # Засечка должна быть косой относительно дуги,
    # как обычная засечка размера, а не радиальной.
    tick_angle = math.radians(45)

    tx, ty = normalize(tangent)

    tick_dx = tx * math.cos(tick_angle) - ty * math.sin(tick_angle)
    tick_dy = tx * math.sin(tick_angle) + ty * math.cos(tick_angle)

    half = size / 2

    msp.add_line(
        (
            point[0] - tick_dx * half,
            point[1] - tick_dy * half,
        ),
        (
            point[0] + tick_dx * half,
            point[1] + tick_dy * half,
        ),
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )


def add_profile_path(
    msp,
    points: list[tuple[float, float, float]],
    width: float,
):
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

def add_point_unique(
    points: list[tuple[float, float, float]],
    point: tuple[float, float, float],
):
    if not points:
        points.append(point)
        return

    last_x, last_y, _ = points[-1]
    x, y, _ = point

    if abs(last_x - x) < 0.0001 and abs(last_y - y) < 0.0001:
        return

    points.append(point)


def get_vector(
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    return end[0] - start[0], end[1] - start[1]


def normalize(vector: tuple[float, float]) -> tuple[float, float]:
    x, y = vector
    length = math.sqrt(x * x + y * y)

    if length == 0:
        raise ValueError("Zero length vector")

    return x / length, y / length


def get_left_normal(
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    dx, dy = normalize(get_vector(start, end))
    return -dy, dx


def get_right_normal(
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    dx, dy = normalize(get_vector(start, end))
    return dy, -dx


def offset_point(
    point: tuple[float, float],
    normal: tuple[float, float],
    distance: float,
) -> tuple[float, float]:
    return (
        point[0] + normal[0] * distance,
        point[1] + normal[1] * distance,
    )


def get_angle_degrees(
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx, dy = get_vector(start, end)
    return math.degrees(math.atan2(dy, dx))


def build_named_lines(
    template: dict,
    parameters: dict[str, float],
) -> dict[str, dict[str, tuple[float, float]]]:
    profile = template["profile"]

    if profile.get("type") != "connected_path":
        raise ValueError("Only profile.type='connected_path' is supported")

    lines = {}

    for element in profile["elements"]:
        if element["type"] != "line":
            raise ValueError(f"Unsupported profile element type: {element['type']}")

        name = element["name"]
        start = resolve_point(element["start"], parameters)
        end = resolve_point(element["end"], parameters)

        lines[name] = {
            "start": start,
            "end": end,
        }

    return lines


def build_profile_path(
    lines: dict[str, dict[str, tuple[float, float]]],
    template: dict,
) -> list[tuple[float, float, float]]:
    profile = template["profile"]
    points: list[tuple[float, float, float]] = []

    for element in profile["elements"]:
        name = element["name"]
        line = lines[name]

        start = line["start"]
        end = line["end"]

        add_point_unique(points, (start[0], start[1], 0))
        add_point_unique(points, (end[0], end[1], 0))

    return points


def draw_profile(
    msp,
    template: dict,
    lines: dict[str, dict[str, tuple[float, float]]],
):
    profile_width = get_template_default(
        template=template,
        name="profile_width",
        fallback=CAD_STYLES["profile"]["width"],
    )

    points = build_profile_path(lines, template)

    add_profile_path(
        msp=msp,
        points=points,
        width=profile_width,
    )


def draw_parallel_dimension(
    msp,
    dim: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, tuple[float, float]]],
):
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

    msp.add_line(
        d1,
        d2,
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )

    profile_gap = CAD_STYLES["profile"]["width"] * 2

    e1 = offset_point(p1, normal, profile_gap)
    e2 = offset_point(p2, normal, profile_gap)

    msp.add_line(
        e1,
        d1,
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )

    msp.add_line(
        e2,
        d2,
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )

    dimension_direction = get_vector(d1, d2)

    add_tick(msp, d1, direction=dimension_direction, size=15)
    add_tick(msp, d2, direction=dimension_direction, size=15)

    mid = (
        (d1[0] + d2[0]) / 2,
        (d1[1] + d2[1]) / 2,
    )

    text_shift = 8
    text_position = offset_point(mid, normal, text_shift)

    if dim.get("text_rotation") == "auto":
        text_rotation = get_angle_degrees(d1, d2)
    else:
        text_rotation = dim.get("text_rotation", 0)

    add_text(
        msp=msp,
        text=fmt(parameters[param_name]),
        position=text_position,
        height=dim.get("text_height", CAD_STYLES["text"]["height"]),
        rotation=text_rotation,
    )


# -----------------------------
# Крючки
# -----------------------------

def rotate_clockwise(vector: tuple[float, float]) -> tuple[float, float]:
    x, y = vector
    return y, -x


def rotate_counterclockwise(vector: tuple[float, float]) -> tuple[float, float]:
    x, y = vector
    return -y, x


def draw_single_hook(
    msp,
    hook: dict,
    lines: dict[str, dict[str, tuple[float, float]]],
    template: dict,
):
    attach_to = hook["attach_to"]
    position = hook["position"]

    if attach_to not in lines:
        raise ValueError(f"Hook target line not found: {attach_to}")

    line = lines[attach_to]
    line_start = line["start"]
    line_end = line["end"]

    width = get_template_default(
        template=template,
        name="profile_width",
        fallback=CAD_STYLES["profile"]["width"],
    )

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

        p0 = (
            base[0] + line_direction[0] * join_overlap,
            base[1] + line_direction[1] * join_overlap,
        )

        p1 = base

        p2 = (
            base[0] + side_direction[0] * radius,
            base[1] + side_direction[1] * radius,
        )

        p3 = (
            p2[0] + line_direction[0] * length,
            p2[1] + line_direction[1] * length,
        )

        points = [
            (p0[0], p0[1], 0),
            (p1[0], p1[1], bulge),
            (p2[0], p2[1], 0),
            (p3[0], p3[1], 0),
        ]

        inner_patch_start = (
            p2[0] - line_direction[0] * inner_join_overlap,
            p2[1] - line_direction[1] * inner_join_overlap,
        )

        inner_patch_end = p3

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

        p0 = (
            base[0] + back_direction[0] * join_overlap,
            base[1] + back_direction[1] * join_overlap,
        )

        p1 = base

        p2 = (
            base[0] + side_direction[0] * radius,
            base[1] + side_direction[1] * radius,
        )

        p3 = (
            p2[0] + back_direction[0] * length,
            p2[1] + back_direction[1] * length,
        )

        points = [
            (p0[0], p0[1], 0),
            (p1[0], p1[1], bulge),
            (p2[0], p2[1], 0),
            (p3[0], p3[1], 0),
        ]

        inner_patch_start = (
            p2[0] - back_direction[0] * inner_join_overlap,
            p2[1] - back_direction[1] * inner_join_overlap,
        )

        inner_patch_end = p3

    else:
        raise ValueError(f"Unknown hook position: {position}")

    add_profile_path(
        msp=msp,
        points=points,
        width=width,
    )

    add_profile_path(
        msp=msp,
        points=[
            (inner_patch_start[0], inner_patch_start[1], 0),
            (inner_patch_end[0], inner_patch_end[1], 0),
        ],
        width=width,
    )

    label = hook.get("label")

    if label:
        add_hook_label(
            msp=msp,
            text=label,
            base=base,
            line_direction=line_direction,
            side_direction=side_direction,
            position=position,
            hook=hook,
        )

def draw_hooks(
    msp,
    template: dict,
    lines: dict[str, dict[str, tuple[float, float]]],
    parameters: dict[str, float],
):
    width = get_template_default(
        template=template,
        name="profile_width",
        fallback=CAD_STYLES["profile"]["width"],
    )

    for hook in template.get("hooks", []):
        hook_type = hook.get("type")

        if hook_type == "hook":
            draw_single_hook(
                msp=msp,
                hook=hook,
                lines=lines,
                template=template,
            )

        elif hook_type == "line":
            start = resolve_point(hook["start"], parameters)
            end = resolve_point(hook["end"], parameters)

            add_profile_path(
                msp=msp,
                points=[
                    (start[0], start[1], 0),
                    (end[0], end[1], 0),
                ],
                width=width,
            )

        else:
            raise ValueError(f"Unknown hook type: {hook_type}")


# -----------------------------
# Маркеры толщины / служебные маркеры
# -----------------------------

def add_triangle_marker(
    msp,
    tip: tuple[float, float],
    line_direction: tuple[float, float],
    side_direction: tuple[float, float],
    height: float = 12,
    depth: float = 10,
):
    """
    Рисует пустой треугольник возле линии.

    tip — вершина треугольника, которая касается линии.
    line_direction — направление линии.
    side_direction — сторона, куда уходит тело треугольника.
    """

    dx, dy = normalize(line_direction)
    sx, sy = normalize(side_direction)

    base_center = (
        tip[0] + sx * depth,
        tip[1] + sy * depth,
    )

    half_height = height / 2

    p1 = (
        base_center[0] - dx * half_height,
        base_center[1] - dy * half_height,
    )

    p2 = tip

    p3 = (
        base_center[0] + dx * half_height,
        base_center[1] + dy * half_height,
    )

    msp.add_lwpolyline(
        [p1, p2, p3, p1],
        dxfattribs={
            "layer": DIM_LAYER,
            "color": CAD_STYLES["dimensions"]["color"],
            "lineweight": CAD_STYLES["dimensions"]["lineweight"],
        },
    )


def draw_markers(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, tuple[float, float]]],
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

        point = (
            start[0] + line_vector[0] * position_value,
            start[1] + line_vector[1] * position_value,
        )

        side = marker.get("side", "left")

        if side == "left":
            side_direction = get_left_normal(start, end)
        elif side == "right":
            side_direction = get_right_normal(start, end)
        else:
            raise ValueError(f"Unknown marker side: {side}")

        offset = resolve_value(marker.get("offset", 0), parameters)

        tip = offset_point(
            point=point,
            normal=side_direction,
            distance=offset,
        )

        height = resolve_value(marker.get("height", 12), parameters)
        depth = resolve_value(marker.get("depth", 10), parameters)

        add_triangle_marker(
            msp=msp,
            tip=tip,
            line_direction=line_direction,
            side_direction=side_direction,
            height=height,
            depth=depth,
        )


def draw_dimensions(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, tuple[float, float]]],
):
    for dim in template.get("dimensions", []):
        dim_type = dim.get("type")

        if dim_type == "parallel_to_line":
            draw_parallel_dimension(
                msp=msp,
                dim=dim,
                parameters=parameters,
                lines=lines,
            )
        else:
            raise ValueError(f"Unknown dimension type: {dim_type}")


def draw_angle_marks(
    msp,
    template: dict,
    parameters: dict[str, float],
    lines: dict[str, dict[str, tuple[float, float]]],
):
    for mark in template.get("angle_marks", []):
        if not mark.get("enabled", False):
            continue

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

        msp.add_arc(
            center=center,
            radius=radius,
            start_angle=draw_angle_1,
            end_angle=draw_angle_2,
            dxfattribs={
                "layer": DIM_LAYER,
                "color": CAD_STYLES["dimensions"]["color"],
                "lineweight": CAD_STYLES["dimensions"]["lineweight"],
            },
        )

        angle_tick_size = resolve_value(mark.get("tick_size", 15), parameters)

        add_angle_tick(
            msp=msp,
            center=center,
            radius=radius,
            angle_degrees=draw_angle_1,
            size=angle_tick_size,
        )

        add_angle_tick(
            msp=msp,
            center=center,
            radius=radius,
            angle_degrees=draw_angle_2,
            size=angle_tick_size,
        )

        mid_angle_degrees = (draw_angle_1 + draw_angle_2) / 2
        mid_angle = math.radians(mid_angle_degrees)

        text_radius = radius + resolve_value(mark.get("text_offset", 8), parameters)

        text_position = (
            center[0] + math.cos(mid_angle) * text_radius,
            center[1] + math.sin(mid_angle) * text_radius,
        )

        add_text(
            msp=msp,
            text=f"{fmt(parameters[param_name])}°",
            position=text_position,
            height=mark.get("text_height", CAD_STYLES["text"]["height"]),
            rotation=mark.get("text_rotation", 0),
        )

def generate_dxf(template: dict, output_path: Path, parameters: dict[str, float]) -> None:
    doc = setup_document()
    msp = doc.modelspace()

    lines = build_named_lines(
        template=template,
        parameters=parameters,
    )

    draw_profile(
        msp=msp,
        template=template,
        lines=lines,
    )

    draw_hooks(
        msp=msp,
        template=template,
        lines=lines,
        parameters=parameters,
    )

    draw_dimensions(
        msp=msp,
        template=template,
        parameters=parameters,
        lines=lines,
    )

    draw_markers(
        msp=msp,
        template=template,
        parameters=parameters,
        lines=lines,
    )

    draw_angle_marks(
        msp=msp,
        template=template,
        parameters=parameters,
        lines=lines,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(output_path)
