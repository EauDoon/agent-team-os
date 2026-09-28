"""Validate the JSON Schema subset used by this package, without dependencies.

This is a contract checker, not a general JSON Schema implementation. It never
loads remote references. Unsupported assertion keywords fail explicitly.
"""

from __future__ import annotations

import json
import math

_MAX_EXACT_INTEGER = 2 ** 53


def _json_model(item: object) -> object:
    """Collapse numerically equal JSON numbers without collapsing booleans."""
    if isinstance(item, bool) or item is None or isinstance(item, str):
        return item
    if isinstance(item, int):
        return item
    if isinstance(item, float):
        if math.isfinite(item) and item.is_integer() and abs(item) <= _MAX_EXACT_INTEGER:
            return int(item)
        return item
    if isinstance(item, list):
        return [_json_model(part) for part in item]
    if isinstance(item, dict):
        return {key: _json_model(part) for key, part in item.items()}
    return item


def _canonical(item: object) -> str:
    return json.dumps(_json_model(item), sort_keys=True, ensure_ascii=True, allow_nan=False)


def is_json_integer(value: object) -> bool:
    """A JSON integer is a finite number with no fractional part.

    Draft 2020-12 counts 1.0 and -0 as integers. Booleans stay booleans.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value) and value.is_integer()


KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "default",
    "type", "const", "enum", "required", "properties", "additionalProperties",
    "minLength", "minItems", "maxItems", "items", "uniqueItems", "minimum",
    "maximum", "allOf", "if", "then", "else",
}


class _ContractLimit(Exception):
    """Checker limit, not a schema mismatch. Callers must not treat it as `else`."""

    def __init__(self, path: str) -> None:
        self.path = path


def violations(value: object, schema: dict, *, root: dict | None = None,
               path: str = "$", depth: int = 0) -> list[str]:
    """Return located violations; reject excessive nesting and unknown rules."""
    try:
        return _violations(value, schema, root=root, path=path, depth=depth)
    except _ContractLimit as exc:
        return [f"{exc.path}: maximum contract depth exceeded"]


def _violations(value: object, schema: dict, *, root: dict | None = None,
                path: str = "$", depth: int = 0) -> list[str]:
    if depth > 64:
        raise _ContractLimit(path)
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path}: number must be finite"]
    root = schema if root is None else root
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    errors: list[str] = []

    def check(child: object, spec: dict, location: str = path) -> list[str]:
        return _violations(child, spec, root=root, path=location, depth=depth + 1)

    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise ValueError("only local JSON Pointer references are supported")
        target = root
        try:
            for token in ref[2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError) as exc:
            raise ValueError("unresolved local schema reference") from exc
        errors.extend(check(value, target))
    kinds = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "boolean": isinstance(value, bool),
        "integer": is_json_integer(value),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "null": value is None,
    }
    if "type" in schema and not kinds.get(schema["type"], False):
        return errors + [f"{path}: expected {schema['type']}"]
    # JSON equality must distinguish true from 1, and must treat 1 and 1.0 as one number.
    canonical = _canonical
    if "const" in schema and canonical(value) != canonical(schema["const"]):
        errors.append(f"{path}: does not match const")
    if "enum" in schema and canonical(value) not in [canonical(x) for x in schema["enum"]]:
        errors.append(f"{path}: value is outside enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                errors.extend(check(item, properties[key], f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}.{key}: unknown field")
            elif isinstance(additional, dict):
                errors.extend(check(item, additional, f"{path}.{key}"))
            elif additional is not True:
                raise ValueError("unsupported additionalProperties schema")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        errors.append(f"{path}: string is too short")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: too few items")
        if len(value) > schema.get("maxItems", len(value)):
            # Reject oversized collections before visiting their items or producing
            # one diagnostic per item. The invalid size is already decisive.
            return errors + [f"{path}: too many items"]
        if schema.get("uniqueItems") and len({canonical(x) for x in value}) != len(value):
            errors.append(f"{path}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(check(item, schema["items"], f"{path}[{index}]"))
    if kinds["number"]:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    for spec in schema.get("allOf", []):
        errors.extend(check(value, spec))
    if "if" in schema:
        branch = "else" if check(value, schema["if"]) else "then"
        if branch in schema:
            errors.extend(check(value, schema[branch]))
    return errors
