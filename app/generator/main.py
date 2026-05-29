from pathlib import Path

from .angles import draw_angle_marks
from .dimensions import draw_dimensions
from .drawing import setup_document
from .hooks import draw_hooks
from .markers import draw_markers
from .obstacles import build_obstacle_lines
from .profile import build_named_lines, draw_profile


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
