import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ('.github/workflows/ci.yml', '.github/workflows/release.yml')


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def step_block(text: str, start: int) -> str:
    """Return one workflow step: from its `- uses:` line to the next step."""
    following = re.compile(r'(?m)^\s*- ').search(text, start + 1)
    return text[start:following.start() if following else len(text)]


class WorkflowConfigTests(unittest.TestCase):
    def test_ci_runs_once_per_change(self):
        ci = read('.github/workflows/ci.yml')
        # Branch pushes other than main and every tag push are left to the
        # pull_request event, so a PR no longer runs the matrix twice.
        self.assertRegex(ci, r'(?m)^on:\n  push:\n    branches: \[main\]\n  pull_request:\n')
        self.assertIn('workflow_dispatch:', ci)
        self.assertNotRegex(ci, r'(?m)^\s+tags:')

    def test_ci_is_bounded_and_cancels_superseded_pull_request_runs(self):
        ci = read('.github/workflows/ci.yml')
        self.assertIn('group: ci-${{ github.workflow }}-${{ github.ref }}', ci)
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", ci)
        self.assertRegex(ci, r'(?m)^    timeout-minutes: \d+$')
        self.assertIn('fail-fast: false', ci)
        self.assertIn('os: [ubuntu-latest, windows-latest]', ci)
        self.assertIn('python: ["3.11", "3.14"]', ci)

    def test_ci_verify_path_reads_the_version_through_one_reader(self):
        ci = read('.github/workflows/ci.yml')
        self.assertIn('dist/agent-team-$(python scripts/version.py).zip', ci)
        self.assertNotIn("read_text()", ci)

    def test_every_checkout_drops_its_credentials(self):
        for relative in WORKFLOWS:
            text = read(relative)
            starts = [match.start() for match in re.finditer(r'(?m)^\s*- uses: actions/checkout@', text)]
            self.assertTrue(starts, relative)
            for start in starts:
                with self.subTest(workflow=relative, offset=start):
                    self.assertIn('persist-credentials: false', step_block(text, start))

    def test_every_action_is_pinned_to_a_full_sha_with_its_version(self):
        for relative in WORKFLOWS:
            uses = re.findall(r'(?m)^\s*(?:- )?uses: (.+)$', read(relative))
            self.assertTrue(uses, relative)
            for reference in uses:
                with self.subTest(workflow=relative, uses=reference):
                    self.assertRegex(reference, r'^[\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$')

    def test_release_gates_the_tag_before_building(self):
        release = read('.github/workflows/release.yml')
        gate = release.index('python3 scripts/validate.py --release-tag "$GITHUB_REF_NAME"')
        ancestry = release.index('git merge-base --is-ancestor "$GITHUB_SHA" origin/main')
        build = release.index('python3 scripts/package.py --output dist')
        self.assertLess(gate, ancestry)
        self.assertLess(ancestry, build)
        self.assertLess(release.index('python3 -m unittest discover -s tests -v'), build)
        self.assertLess(release.index('python3 evals/runner.py'), build)
        self.assertIn('fetch-depth: 0', release)
        self.assertIn('dist/agent-team-$(python3 scripts/version.py).zip', release)
        self.assertIn('VERSION="$(python3 scripts/version.py)"', release)
        self.assertNotIn('GITHUB_REF_NAME#v', release)

    def test_release_permissions_are_scoped_to_the_job(self):
        release = read('.github/workflows/release.yml')
        workflow_level, job_level = release.split('\njobs:\n', 1)
        self.assertRegex(workflow_level, r'(?m)^permissions:\n  contents: read$')
        self.assertIn('group: release-${{ github.ref }}', workflow_level)
        self.assertIn('cancel-in-progress: false', workflow_level)
        self.assertRegex(job_level, r'(?m)^    timeout-minutes: \d+$')
        self.assertRegex(job_level, r'(?m)^    permissions:\n      contents: write\n      id-token: write\n'
                                    r'      attestations: write\n      artifact-metadata: write$')
        self.assertNotIn('continue-on-error', release)

    def test_release_attests_the_verified_archive_before_publishing(self):
        release = read('.github/workflows/release.yml')
        attest = release.index('uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2')
        self.assertLess(release.index('sha256sum -c'), attest)
        self.assertLess(attest, release.index('gh release create'))
        self.assertIn('subject-path: dist/agent-team-*.zip', release)

    def test_dependabot_updates_the_pinned_actions(self):
        config = read('.github/dependabot.yml')
        self.assertRegex(config, r'(?m)^version: 2$')
        self.assertIn('package-ecosystem: github-actions', config)
        self.assertRegex(config, r'(?m)^\s+directory: /$')
        self.assertIn('interval: weekly', config)
        self.assertIn('prefix: ci', config)

    def test_make_ci_runs_the_ci_steps_in_order(self):
        makefile = read('Makefile')
        self.assertRegex(makefile, r'(?m)^package: validate test evals$')
        self.assertRegex(makefile, r'(?m)^ci: package$')
        self.assertRegex(makefile, r'(?m)^PKG_VERSION := \$\(shell \$\(PYTHON\) scripts/version\.py\)$')


if __name__ == '__main__':
    unittest.main()
