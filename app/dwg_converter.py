import subprocess
from pathlib import Path

from config import ODA_CONVERTER_EXE


def convert_dxf_to_dwg(dxf_path: Path, dwg_path: Path) -> bool:
    """
    Конвертирует DXF в DWG через ODA File Converter.

    Если ODA ещё не установлен — просто возвращает False.
    Это позволит нам сначала проверить DXF.
    """

    if not ODA_CONVERTER_EXE.exists():
        return False

    source_dir = dxf_path.parent
    target_dir = dwg_path.parent

    cmd = [
        str(ODA_CONVERTER_EXE),
        str(source_dir),
        str(target_dir),
        "ACAD2018",
        "DWG",
        "0",
        "1",
        dxf_path.name,
    ]

    subprocess.run(cmd, check=True)

    return dwg_path.exists()
