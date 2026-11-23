"""Release gates must require each configured Circus jobset on the commit."""

import os
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release.sh"


class CircusReleaseGateTest(unittest.TestCase):
    def check_gate(self, statuses, *, jobsets="main main-arm"):
        script = r'''
source "$1"
gh() {
  [[ "$2" == 'repos/{owner}/{repo}/commits/deadbeef/status' ]] || exit 43
  printf '%s\n' "$TEST_STATUSES"
}
sleep() { exit 42; }
wait_for_circus deadbeef
'''
        return subprocess.run(
            ["bash", "-c", script, "test", str(SCRIPT)],
            env={**os.environ, "TEST_STATUSES": statuses, "RELEASE_CIRCUS_JOBSETS": jobsets},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_both_jobsets_must_pass(self):
        result = self.check_gate("circus/jobset/main\tsuccess\ncircus/jobset/main-arm\tsuccess")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_arm_blocks_green_x86(self):
        result = self.check_gate("circus/jobset/main\tsuccess\ncircus/jobset/main-arm\tfailure")
        self.assertEqual(result.returncode, 1)

    def test_missing_or_pending_jobset_does_not_pass(self):
        for statuses in (
            "circus/jobset/main\tsuccess",
            "circus/jobset/main\tsuccess\ncircus/jobset/main-arm\tpending",
        ):
            with self.subTest(statuses=statuses):
                self.assertEqual(self.check_gate(statuses).returncode, 42)

    def test_single_architecture_can_be_configured(self):
        result = self.check_gate("circus/jobset/main\tsuccess", jobsets="main")
        self.assertEqual(result.returncode, 0, result.stderr)


class WorkflowGateTest(unittest.TestCase):
    def wait(self, runs):
        script = r'''
source "$1"
gh() { printf '%s\n' "$TEST_RUNS"; }
sleep() { exit 42; }
wait_for_workflow deadbeef build
'''
        return subprocess.run(
            ["bash", "-c", script, "test", str(SCRIPT)],
            env={**os.environ, "TEST_RUNS": runs},
            capture_output=True,
            text=True,
            check=False,
        )

    def test_finished_runs_pass(self):
        result = self.wait("1\tcompleted\tsuccess\n2\tcompleted\tsuccess")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unfinished_or_missing_runs_wait(self):
        # A run that is queued, running, or not created yet keeps the gate
        # waiting; its empty conclusion must never read as a failure.
        for runs in ("", "1\tqueued\t", "1\tcompleted\tsuccess\n2\tin_progress\t"):
            with self.subTest(runs=runs):
                self.assertEqual(self.wait(runs).returncode, 42)

    def test_failed_run_blocks(self):
        result = self.wait("1\tcompleted\tfailure")
        self.assertEqual(result.returncode, 1)
        self.assertIn("did not succeed", result.stderr)


if __name__ == "__main__":
    unittest.main()
