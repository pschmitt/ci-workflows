"""Fail closed unless cached Circus outputs match a trusted workflow source."""

import json
import os
import re
import sys
import urllib.error
import urllib.request


def fetch_json(path, token):
    url = "https://api.github.com/" + path
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Public repository metadata is readable without authentication even
        # when a caller intentionally gives its workflow token fewer scopes.
        if error.code not in {403, 404}:
            raise
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": headers["Accept"]}), timeout=30) as response:
        return json.load(response)


def verify(env, fetch=fetch_json):
    sha = env.get("GITHUB_SHA", "")
    repository = env.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid workflow source identity")
    if env.get("EVENT_NAME") == "status":
        if env.get("PR_NUMBER") or env.get("PR_SHA"):
            raise ValueError("A main artifact status cannot identify a pull request")
        if (env.get("STATUS_CONTEXT"), env.get("STATUS_STATE"), env.get("STATUS_SHA")) != ("circus/artifacts", "success", sha):
            raise ValueError("The main Circus artifact status does not match")
        return
    number = env.get("PR_NUMBER", "")
    pr_sha = env.get("PR_SHA", "")
    if env.get("EVENT_NAME") != "workflow_dispatch" or env.get("GITHUB_REF") != "refs/heads/main" or not re.fullmatch(r"[1-9][0-9]*", number) or not re.fullmatch(r"[0-9a-f]{40}", pr_sha):
        raise ValueError("Invalid Circus pull request dispatch")
    token = env.get("GH_TOKEN", "")
    if not token:
        raise ValueError("Missing GitHub token")
    repo = fetch(f"repos/{repository}", token)
    pr = fetch(f"repos/{repository}/pulls/{number}", token)
    owner_id = (repo.get("owner") or {}).get("id")
    head = pr.get("head") or {}
    if not all([
        isinstance(owner_id, int) and not isinstance(owner_id, bool) and owner_id > 0,
        (pr.get("user") or {}).get("id") == owner_id,
        pr.get("number") == int(number),
        pr.get("state") == "open",
        pr.get("draft") is False,
        (pr.get("base") or {}).get("ref") == "main",
        (head.get("repo") or {}).get("full_name") == repository,
        head.get("sha") == pr_sha,
    ]):
        raise ValueError("Pull request is not trusted or its head has changed")
    statuses = fetch(f"repos/{repository}/commits/{pr_sha}/status", token).get("statuses", [])
    if not any(s.get("context") == "circus/pr-artifacts" and s.get("state") == "success" for s in statuses):
        raise ValueError("Circus PR artifacts are not ready for this commit")


if __name__ == "__main__":
    try:
        verify(os.environ)
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError, json.JSONDecodeError):
        print("Circus artifact verification failed.", file=sys.stderr)
        sys.exit(1)
