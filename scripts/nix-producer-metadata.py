#!/usr/bin/env python3
"""Create source-bound metadata for a reusable Nix producer artifact."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


def fail(message: str) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(1)


sha_pattern = re.compile(r"[0-9a-f]{40}")
source_sha = os.environ.get("GITHUB_SHA", "")
if not sha_pattern.fullmatch(source_sha):
    fail("Invalid workflow source revision.")

try:
    checked_out_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
except (OSError, subprocess.CalledProcessError):
    fail("Could not verify the checked-out source revision.")
if checked_out_sha != source_sha:
    fail("Checked-out source revision does not match the workflow revision.")

event_name = os.environ.get("GITHUB_EVENT_NAME", "")
pr_head_sha = None
if event_name == "pull_request":
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        pr_head_sha = event["pull_request"]["head"]["sha"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        fail("Could not read the pull request source revision.")
    if not isinstance(pr_head_sha, str) or not sha_pattern.fullmatch(pr_head_sha):
        fail("Invalid pull request source revision.")

run_id = os.environ.get("GITHUB_RUN_ID", "")
run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
if (
    not run_id.isdecimal()
    or not run_attempt.isdecimal()
    or int(run_id) < 1
    or int(run_attempt) < 1
):
    fail("Invalid workflow run identity.")

if len(sys.argv) != 2:
    fail("Expected one output path.")

metadata = {
    "pr_head_sha": pr_head_sha,
    "run_attempt": int(run_attempt),
    "run_id": int(run_id),
    "source_sha": source_sha,
}
Path(sys.argv[1]).write_text(json.dumps(metadata, separators=(",", ":")) + "\n", encoding="utf-8")
