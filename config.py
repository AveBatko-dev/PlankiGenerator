from pathlib import Path

BASE_DIR = Path(__file__).parent

DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = DATA_DIR / "templates"
PREVIEWS_DIR = DATA_DIR / "previews"
OUTPUT_DIR = DATA_DIR / "output"

ODA_CONVERTER_EXE = Path(
    r"C:\Program Files\ODA\ODAFileConverter 27.1.0\ODAFileConverter.exe"
)

CAD_STYLES = {
    "profile": {
        "layer": "PROFILE",
        "color": 7,
        "lineweight": 100,
        "width": 3
    },
    "dimensions": {
        "layer": "DIMENSIONS",
        "color": 8,
        "lineweight": 25
    },
    "text": {
        "layer": "TEXT",
        "color": 7,
        "lineweight": 25,
        "height": 8
    },
}
