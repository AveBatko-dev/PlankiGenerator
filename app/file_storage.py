from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR


def create_output_paths(template_code: str) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{template_code}_{timestamp}"

    dxf_path = OUTPUT_DIR / f"{base_name}.dxf"
    dwg_path = OUTPUT_DIR / f"{base_name}.dwg"

    return dxf_path, dwg_path
