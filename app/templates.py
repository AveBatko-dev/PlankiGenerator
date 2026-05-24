import json

from config import TEMPLATES_DIR


def load_template(template_code: str) -> dict:
    template_path = TEMPLATES_DIR / f"{template_code}.json"

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_code}")

    with open(template_path, "r", encoding="utf-8") as file:
        return json.load(file)
