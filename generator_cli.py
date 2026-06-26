import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from app.dwg_converter import convert_dxf_to_dwg
from app.dxf_generator import generate_dxf
from app.file_storage import create_output_paths
from app.png_generator import generate_pngs
from app.templates import load_template
from config import OUTPUT_DIR, TEMPLATES_DIR


COMMANDS_FILE = Path("comandes")
PARAM_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9_]*\b")
KNOWN_FUNCTIONS = {"COS", "SIN", "TAN", "RADIANS", "DEGREES", "PI"}
PARAM_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6}


def normalize_template_code(value: str) -> str:
    value = value.strip().lower()
    if value.isdigit():
        return f"pl_{value}"
    return value


def template_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)$", path.stem)
    if match:
        return int(match.group(1)), path.stem
    return 10_000, path.stem


def param_sort_key(name: str) -> tuple[int, int, str]:
    if name in PARAM_ORDER:
        return PARAM_ORDER[name], 0, name

    match = re.fullmatch(r"([A-F])_PLUS_(\d+)", name)
    if match:
        return PARAM_ORDER[match.group(1)], int(match.group(2)), name

    angle_match = re.fullmatch(r"K(\d+)", name)
    if angle_match:
        return 100, int(angle_match.group(1)), name

    return 50, 0, name


def is_parameter_token(token: str) -> bool:
    if token in KNOWN_FUNCTIONS:
        return False
    if re.fullmatch(r"Z\d+", token):
        return False
    return bool(
        re.fullmatch(r"[A-F]", token)
        or re.fullmatch(r"K\d+", token)
        or re.fullmatch(r"[A-F]_PLUS_\d+", token)
    )


def collect_string_tokens(value: Any, tokens: set[str]) -> None:
    if isinstance(value, dict):
        for child in value.values():
            collect_string_tokens(child, tokens)
    elif isinstance(value, list):
        for child in value:
            collect_string_tokens(child, tokens)
    elif isinstance(value, str):
        for token in PARAM_TOKEN_RE.findall(value.upper()):
            if is_parameter_token(token):
                tokens.add(token)


def get_template_parameters(template: dict[str, Any]) -> list[str]:
    tokens: set[str] = set()
    collect_string_tokens(template, tokens)
    return sorted(tokens, key=param_sort_key)


def load_command_defaults(path: Path = COMMANDS_FILE) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)

    defaults: dict[str, dict[str, float]] = {}
    for row in rows:
        template_code = normalize_template_code(str(row.get("template_code", "")))
        parameters = row.get("parameters", {})
        if template_code and isinstance(parameters, dict):
            defaults[template_code] = {
                str(key).upper(): float(value)
                for key, value in parameters.items()
            }
    return defaults


def list_templates() -> list[Path]:
    return sorted(TEMPLATES_DIR.glob("pl_*.json"), key=template_sort_key)


def parse_param_args(values: list[str] | None) -> dict[str, float]:
    parameters: dict[str, float] = {}
    for raw_value in values or []:
        if "=" not in raw_value:
            raise ValueError(f"Parameter must use NAME=VALUE format: {raw_value}")
        name, value = raw_value.split("=", 1)
        parameters[name.strip().upper()] = parse_float(value)
    return parameters


def parse_float(value: str) -> float:
    return float(value.strip().replace(",", "."))


def generate_drawing(template_code: str, parameters: dict[str, float]) -> dict[str, Any]:
    template = load_template(template_code)
    dxf_path, dwg_path, png_original_path, png_100x200_path = create_output_paths(
        template_code
    )

    document = generate_dxf(
        template=template,
        output_path=dxf_path,
        parameters=parameters,
    )
    generate_pngs(
        document=document,
        original_path=png_original_path,
        thumbnail_path=png_100x200_path,
    )

    dwg_created = False
    dwg_error = None
    try:
        dwg_created = convert_dxf_to_dwg(dxf_path=dxf_path, dwg_path=dwg_path)
    except Exception as error:
        dwg_error = str(error)

    return {
        "template_code": template_code,
        "dxf_path": dxf_path,
        "dwg_path": dwg_path if dwg_created else None,
        "png_original_path": png_original_path,
        "png_100x200_path": png_100x200_path,
        "dwg_error": dwg_error,
    }


def print_result(result: dict[str, Any]) -> None:
    print()
    print(f"Done: {result['template_code']}")
    print(f"DXF: {result['dxf_path']}")
    if result["dwg_path"]:
        print(f"DWG: {result['dwg_path']}")
    else:
        print("DWG: not created")
    print(f"PNG: {result['png_original_path']}")
    print(f"PNG 100x200: {result['png_100x200_path']}")
    if result["dwg_error"]:
        print(f"DWG converter error: {result['dwg_error']}")


def prompt_template_code() -> str | None:
    print()
    print("Available templates:")
    for path in list_templates():
        print(f"  {path.stem}")
    print()

    while True:
        value = input("Template number/code (for example 1 or pl_1, q to exit): ").strip()
        if value.lower() in {"q", "quit", "exit"}:
            return None

        template_code = normalize_template_code(value)
        if (TEMPLATES_DIR / f"{template_code}.json").exists():
            return template_code

        print(f"Template not found: {template_code}")


def prompt_parameters(
    template_code: str,
    defaults: dict[str, dict[str, float]],
) -> dict[str, float]:
    template = load_template(template_code)
    required_parameters = get_template_parameters(template)
    template_defaults = defaults.get(template_code, {})

    print()
    print(f"Enter parameters for {template_code}. Press Enter to use value in brackets.")

    parameters: dict[str, float] = {}
    for name in required_parameters:
        default = template_defaults.get(name)
        while True:
            suffix = f" [{default:g}]" if default is not None else ""
            value = input(f"{name}{suffix}: ").strip()
            if not value and default is not None:
                parameters[name] = default
                break
            try:
                parameters[name] = parse_float(value)
                break
            except ValueError:
                print("Enter a number, for example 120 or 120.5")

    return parameters


def run_interactive() -> int:
    defaults = load_command_defaults()

    while True:
        print()
        print("Planki Generator")
        print("1 - Generate one drawing")
        print("2 - Generate all drawings from comandes")
        print("3 - Show output folder path")
        print("0 - Exit")
        choice = input("Choose action: ").strip()

        if choice == "1":
            template_code = prompt_template_code()
            if not template_code:
                continue
            parameters = prompt_parameters(template_code, defaults)
            result = generate_drawing(template_code, parameters)
            print_result(result)
        elif choice == "2":
            generate_from_commands(COMMANDS_FILE)
        elif choice == "3":
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            print(f"Output folder: {OUTPUT_DIR}")
        elif choice == "0":
            return 0
        else:
            print("Unknown action.")


def generate_from_commands(path: Path) -> int:
    if not path.exists():
        print(f"Commands file not found: {path}")
        return 1

    with path.open("r", encoding="utf-8") as file:
        rows = json.load(file)

    total = len(rows)
    failed = 0
    print(f"Generating {total} drawings from {path}...")

    for index, row in enumerate(rows, start=1):
        template_code = normalize_template_code(str(row["template_code"]))
        parameters = {
            str(key).upper(): float(value)
            for key, value in row.get("parameters", {}).items()
        }

        try:
            result = generate_drawing(template_code, parameters)
            print(f"[{index}/{total}] {template_code}: OK")
            print(f"  DXF: {result['dxf_path']}")
            if result["dwg_path"]:
                print(f"  DWG: {result['dwg_path']}")
            if result["dwg_error"]:
                print(f"  DWG converter error: {result['dwg_error']}")
        except Exception as error:
            failed += 1
            print(f"[{index}/{total}] {template_code}: FAILED - {error}")

    print()
    print(f"Finished. Success: {total - failed}, failed: {failed}")
    print(f"Output folder: {OUTPUT_DIR}")
    return 1 if failed else 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Planki drawings without API.")
    parser.add_argument("--all", action="store_true", help="Generate all rows from comandes.")
    parser.add_argument(
        "--commands",
        type=Path,
        default=COMMANDS_FILE,
        help="Path to commands JSON file.",
    )
    parser.add_argument("--template", help="Template code, for example pl_1 or 1.")
    parser.add_argument(
        "--param",
        action="append",
        help="Drawing parameter in NAME=VALUE format. Can be repeated.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        if args.all:
            return generate_from_commands(args.commands)

        if args.template:
            template_code = normalize_template_code(args.template)
            parameters = parse_param_args(args.param)
            result = generate_drawing(template_code, parameters)
            print_result(result)
            return 0

        return run_interactive()
    except KeyboardInterrupt:
        print()
        print("Stopped.")
        return 130
    except Exception as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
