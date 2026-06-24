from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR


def create_output_paths(template_code: str) -> tuple[Path, Path, Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"{template_code}_{timestamp}"

    dxf_path = OUTPUT_DIR / f"{base_name}.dxf"
    dwg_path = OUTPUT_DIR / f"{base_name}.dwg"
    png_original_path = OUTPUT_DIR / f"{base_name}_original.png"
    png_100x200_path = OUTPUT_DIR / f"{base_name}_100x200.png"

    return dxf_path, dwg_path, png_original_path, png_100x200_path
