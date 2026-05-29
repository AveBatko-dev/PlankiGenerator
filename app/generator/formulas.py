from typing import Any
import math

from .types import Point


def fmt(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(round(value, 2))


def resolve_value(value: Any, parameters: dict[str, float]) -> float:
    if isinstance(value, str):
        safe_locals = {key: float(val) for key, val in parameters.items()}
        safe_locals.update(
            {
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "radians": math.radians,
                "degrees": math.degrees,
                "pi": math.pi,
            }
        )

        try:
            return float(eval(value, {"__builtins__": {}}, safe_locals))
        except NameError:
            raise ValueError(f"Missing parameter in expression: {value}")
        except Exception as error:
            raise ValueError(f"Invalid expression: {value}. {error}")

    return float(value)


def resolve_point(point: list[Any], parameters: dict[str, float]) -> Point:
    return resolve_value(point[0], parameters), resolve_value(point[1], parameters)
