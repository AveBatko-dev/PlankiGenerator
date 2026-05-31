import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

from config import CAD_STYLES
from .geometry import normalize
from .settings import PROFILE_LAYER, TEXT_LAYER, get_dimension_attribs, ROUND_DISC_SEGMENTS
from .types import Point, Segment


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


def add_centered_text(msp, text: str, position: Point, height: float | None = None, rotation: float = 0):
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
    ).set_placement(position, align=TextEntityAlignment.MIDDLE_CENTER)


def estimate_text_size(text: str, height: float) -> tuple[float, float]:
    return max(height * 0.65 * len(text), height * 0.65), height


def add_profile_path(msp, points: list[tuple[float, float, float]], width: float):
    if len(points) < 2:
        return

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


def add_filled_disc(msp, center: Point, radius: float, segments: int = ROUND_DISC_SEGMENTS):
    if radius <= 0:
        return

    points = []
    for index in range(max(8, segments)):
        angle = 2 * math.pi * index / max(8, segments)
        points.append((center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius))

    hatch = msp.add_hatch(
        color=CAD_STYLES["profile"]["color"],
        dxfattribs={"layer": CAD_STYLES["profile"]["layer"]},
    )
    hatch.paths.add_polyline_path(points, is_closed=True)


def add_rounded_profile_path(msp, points: list[tuple[float, float, float]], width: float):
    add_profile_path(msp=msp, points=points, width=width)

    radius = width / 2
    seen: set[tuple[int, int]] = set()
    for point in points:
        center = (point[0], point[1])
        key = (round(center[0] * 1000), round(center[1] * 1000))
        if key in seen:
            continue
        seen.add(key)
        add_filled_disc(msp=msp, center=center, radius=radius)


def get_tick_segment(position: Point, direction: Point, size: float = 6) -> Segment:
    x, y = position
    dx, dy = normalize(direction)
    angle = math.radians(45)
    tick_dx = dx * math.cos(angle) - dy * math.sin(angle)
    tick_dy = dx * math.sin(angle) + dy * math.cos(angle)
    half = size / 2
    return (x - tick_dx * half, y - tick_dy * half), (x + tick_dx * half, y + tick_dy * half)


def add_tick(msp, position: Point, direction: Point, size: float = 15):
    start, end = get_tick_segment(position=position, direction=direction, size=size)
    msp.add_line(start, end, dxfattribs=get_dimension_attribs())


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
    msp.add_line(start, end, dxfattribs=get_dimension_attribs())
