import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evals.runner as runner

ROOT = Path(__file__).resolve().parents[1]


class EvalRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.cases = self.root / "cases"
        self.cases.mkdir()
        self.tasks_file = self.root / "tasks.json"
        self.tasks = {
            "suite_version": "agent-team-eval/v0.1",
            "tasks": [
                {"id": "alpha", "task_shape": "evidence-extraction", "prompt": "p1",
                 "acceptance": ["one"]},
                {"id": "beta", "task_shape": "uncertainty", "prompt": "p2",
                 "acceptance": ["two", "three"]},
            ],
        }
        self.write_tasks()
        self.write_cases()

    def write_tasks(self, document=None):
        text = document if isinstance(document, str) else json.dumps(self.tasks)
        self.tasks_file.write_text(text, encoding="utf-8")

    def write_cases(self, **changes):
        for task in self.tasks["tasks"]:
            case = dict(task)
            for field, value in changes.get(task["id"], {}).items():
                if value is None:
                    case.pop(field, None)
                else:
                    case[field] = value
            (self.cases / f"{task['id']}.json").write_text(json.dumps(case), encoding="utf-8")

    def run_runner(self, cases=None):
        out, errors = io.StringIO(), io.StringIO()
        with patch.multiple(runner, TASKS_FILE=self.tasks_file, CASES_DIR=cases or self.cases):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
                status = runner.run()
        return status, out.getvalue(), errors.getvalue()

    def test_matching_cases_pass(self):
        self.assertEqual(self.run_runner()[:1], (0,))

    def test_each_case_break_is_reported_and_fails_the_suite(self):
        for defect, changes, expected in [
            ("drifted prompt", {"alpha": {"prompt": "changed"}}, "field 'prompt' differs"),
            ("missing field", {"beta": {"acceptance": None}}, "missing required field: acceptance"),
            ("blank acceptance", {"beta": {"acceptance": ["two", "  "]}},
             "acceptance[1] must be a non-empty string"),
            ("wrong task shape", {"alpha": {"task_shape": []}}, "task_shape must be a string"),
            ("renamed id", {"beta": {"id": "gamma"}}, "does not match filename stem"),
            ("unknown id", {"beta": {"id": "delta"}}, "not present in evals/tasks.json"),
        ]:
            with self.subTest(defect=defect):
                self.setUp()
                self.write_cases(**changes)
                status, out, errors = self.run_runner()
                self.assertEqual(status, 1, errors)
                self.assertIn(expected, out)

    def test_a_case_that_is_not_an_object_is_reported(self):
        (self.cases / "alpha.json").write_text("[1, 2]", encoding="utf-8")
        status, out, errors = self.run_runner()
        self.assertEqual(status, 1)
        self.assertIn("case root must be a JSON object", out)

    def test_a_case_file_that_is_not_json_is_reported(self):
        (self.cases / "alpha.json").write_text("{ not json", encoding="utf-8")
        status, out, errors = self.run_runner()
        self.assertEqual(status, 1)
        self.assertIn("invalid JSON", out)

    def test_a_missing_or_unmatched_case_set_exits_two(self):
        empty = self.root / "empty"
        empty.mkdir()
        extra = self.root / "extra"
        extra.mkdir()
        for path in extra.glob("*.json"):
            path.unlink()
        (self.root / "cases" / "gamma.json").write_text("{}", encoding="utf-8")
        for name, cases in [("no cases", empty), ("unmatched case", extra)]:
            with self.subTest(suite=name):
                status, out, errors = self.run_runner(cases=cases)
                self.assertEqual(status, 2, out)
                self.assertTrue(errors.startswith("FAIL: "), errors)

    def test_an_unusable_rubric_reports_one_line_and_exits_two(self):
        for rubric, document in [
            ("invalid JSON", "{ not json"),
            ("not an object", "[1, 2]"),
            ("no task list", json.dumps({"suite_version": "agent-team-eval/v0.1"})),
            ("task is not an object", json.dumps({"tasks": ["alpha"]})),
            ("missing ID", json.dumps({"tasks": [{"task_shape": "s"}]})),
            ("blank ID", json.dumps({"tasks": [{"id": " "}]})),
            ("duplicate ID", json.dumps({"tasks": [{"id": "alpha"}, {"id": "alpha"}]})),
        ]:
            with self.subTest(rubric=rubric):
                self.setUp()
                self.write_tasks(document)
                status, out, errors = self.run_runner()
                self.assertEqual(status, 2, out)
                self.assertTrue(errors.startswith("FAIL: "), errors)
                self.assertEqual(len(errors.strip().splitlines()), 1, errors)

    def test_a_missing_rubric_reports_one_line_and_exits_two(self):
        self.tasks_file.unlink()
        status, out, errors = self.run_runner()
        self.assertEqual(status, 2)
        self.assertEqual(errors.strip(), "FAIL: evals/tasks.json is unreadable or not valid JSON")

    def test_the_shipped_rubric_and_cases_still_match(self):
        out, errors = io.StringIO(), io.StringIO()
        with patch.multiple(runner, TASKS_FILE=ROOT / "evals" / "tasks.json",
                            CASES_DIR=ROOT / "evals" / "cases"):
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
                status = runner.run()
        self.assertEqual(status, 0, errors.getvalue())
        self.assertIn("Result: 6/6 passed", out.getvalue())


if __name__ == "__main__":
    unittest.main()
