import os
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR",
    str(Path(tempfile.gettempdir()) / "planki_matplotlib"),
)
from ezdxf.addons.drawing import matplotlib
from PIL import Image


THUMBNAIL_SIZE = (200, 100)


def generate_pngs(document, original_path: Path, thumbnail_path: Path) -> None:
    original_path.parent.mkdir(parents=True, exist_ok=True)

    matplotlib.qsave(
        document.modelspace(),
        original_path,
        bg="#FFFFFF",
        dpi=300,
        backend="agg",
    )

    with Image.open(original_path) as image:
        resized = image.resize(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        resized.save(thumbnail_path)
