from typing import Any

from config import CAD_STYLES


PROFILE_LAYER = CAD_STYLES["profile"]["layer"]
DIM_LAYER = CAD_STYLES["dimensions"]["layer"]
TEXT_LAYER = CAD_STYLES["text"]["layer"]

PROFILE_WIDTH_SCALE = 2 / 3
MAIN_PROFILE_WIDTH_FACTOR = 0.5
HOOK_SPAN_FACTOR = 0.5
DIMENSION_HOOK_CLEARANCE_FACTOR = 4 / 3
DIMENSION_LINEWEIGHT = 60
ROUND_DISC_SEGMENTS = 32


def get_template_default(template: dict, name: str, fallback: float) -> float:
    return float(template.get("defaults", {}).get(name, fallback))


def get_base_profile_width(template: dict) -> float:
    return get_template_default(
        template=template,
        name="profile_width",
        fallback=CAD_STYLES["profile"]["width"],
    ) * PROFILE_WIDTH_SCALE


def get_main_profile_width(template: dict) -> float:
    return get_base_profile_width(template=template) * MAIN_PROFILE_WIDTH_FACTOR


def get_hook_width(template: dict) -> float:
    # Крючок всегда той же толщины, что и основной профиль.
    return get_main_profile_width(template=template)


def get_dimension_attribs() -> dict[str, Any]:
    return {
        "layer": DIM_LAYER,
        "color": CAD_STYLES["dimensions"]["color"],
        "lineweight": DIMENSION_LINEWEIGHT,
    }
