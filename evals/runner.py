"""Run the bounded rubric case suite.

This runner converts the entries declared in ``evals/tasks.json`` into a flat
list of per-case JSON files under ``evals/cases/``.  Each case mirrors one
rubric entry verbatim: same id, same task shape, same prompt, same ordered
acceptance checks.

The runner is intentionally a spec-text checker, not a model runner.  Each
case is asserted against three contracts:

1. The case file is well-formed JSON with the required fields.
2. The file name (minus ``.json``) equals the case ``id``.
3. The case payload matches the corresponding entry in ``evals/tasks.json``
   field-for-field (id, task_shape, prompt, and acceptance list).

It prints ``PASS`` or ``FAIL`` for each case and exits 0 only if every case
passes.  The output is plain text so it composes with ``make evals`` and CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "evals" / "cases"
TASKS_FILE = ROOT / "evals" / "tasks.json"

REQUIRED_FIELDS = ("id", "task_shape", "prompt", "acceptance")


def _load_tasks() -> dict:
    with TASKS_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _check_case(case_path: Path, tasks_by_id: dict) -> list:
    problems: list = []

    try:
        with case_path.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(case, dict):
        return ["case root must be a JSON object"]

    for field in REQUIRED_FIELDS:
        if field not in case:
            problems.append(f"missing required field: {field}")

    if "id" in case:
        expected_stem = case_path.stem
        if case["id"] != expected_stem:
            problems.append(
                f"id {case['id']!r} does not match filename stem {expected_stem!r}"
            )

    if "acceptance" in case:
        acceptance = case["acceptance"]
        if not isinstance(acceptance, list) or not acceptance:
            problems.append("acceptance must be a non-empty list")
        else:
            for index, item in enumerate(acceptance):
                if not isinstance(item, str) or not item.strip():
                    problems.append(f"acceptance[{index}] must be a non-empty string")

    if "task_shape" in case and not isinstance(case["task_shape"], str):
        problems.append("task_shape must be a string")

    if "prompt" in case and not isinstance(case["prompt"], str):
        problems.append("prompt must be a string")

    if "id" in case:
        rubric = tasks_by_id.get(case["id"])
        if rubric is None:
            problems.append(f"id {case['id']!r} not present in evals/tasks.json")
        else:
            for field in REQUIRED_FIELDS:
                if case.get(field) != rubric.get(field):
                    problems.append(
                        f"field {field!r} differs from evals/tasks.json"
                    )

    return problems


def run() -> int:
    tasks = _load_tasks()
    tasks_by_id = {task["id"]: task for task in tasks.get("tasks", [])}

    case_paths = sorted(CASES_DIR.glob("*.json"))
    if not case_paths:
        print("FAIL: no case files found under evals/cases/", file=sys.stderr)
        return 2

    rubric_ids = sorted(tasks_by_id)
    case_ids = sorted(path.stem for path in case_paths)
    if case_ids != rubric_ids:
        print(
            "FAIL: case ids "
            f"{case_ids} do not match rubric ids {rubric_ids}",
            file=sys.stderr,
        )
        return 2

    failed = 0
    print(f"Running {len(case_paths)} rubric case(s)")
    for case_path in case_paths:
        problems = _check_case(case_path, tasks_by_id)
        if problems:
            failed += 1
            print(f"FAIL  {case_path.stem}")
            for problem in problems:
                print(f"      - {problem}")
        else:
            print(f"PASS  {case_path.stem}")

    total = len(case_paths)
    passed = total - failed
    print(f"\nResult: {passed}/{total} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
