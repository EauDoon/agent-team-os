"""Validate the JSON Schema subset used by this package, without dependencies.

This is a contract checker, not a general JSON Schema implementation. It never
loads remote references. Unsupported assertion keywords fail explicitly.
"""

from __future__ import annotations

import json
import math


KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "default",
    "type", "const", "enum", "required", "properties", "additionalProperties",
    "minLength", "minItems", "maxItems", "items", "uniqueItems", "minimum",
    "maximum", "allOf", "if", "then", "else",
}


def violations(value: object, schema: dict, *, root: dict | None = None,
               path: str = "$", depth: int = 0) -> list[str]:
    """Return located violations; reject excessive nesting and unknown rules."""
    if depth > 64:
        return [f"{path}: maximum contract depth exceeded"]
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path}: number must be finite"]
    root = schema if root is None else root
    unknown = set(schema) - KEYWORDS
    if unknown:
        raise ValueError(f"unsupported schema keywords: {sorted(unknown)}")
    errors: list[str] = []

    def check(child: object, spec: dict, location: str = path) -> list[str]:
        return violations(child, spec, root=root, path=location, depth=depth + 1)

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
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "null": value is None,
    }
    if "type" in schema and not kinds.get(schema["type"], False):
        return errors + [f"{path}: expected {schema['type']}"]
    # JSON equality must distinguish true from 1, including inside collections.
    canonical = lambda item: json.dumps(item, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if "const" in schema and canonical(value) != canonical(schema["const"]):
        errors.append(f"{path}: does not match const")
    if "enum" in schema and canonical(value) not in [canonical(x) for x in schema["enum"]]:
        errors.append(f"{path}: value is outside enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        for key, item in value.items():
            if key in properties:
                errors.extend(check(item, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{key}: unknown field")
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
