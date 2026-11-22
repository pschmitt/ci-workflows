import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError


PATH = Path(__file__).resolve().parents[1] / ".github/actions/verify-circus-artifacts/verify.py"
SPEC = importlib.util.spec_from_file_location("verify_circus", PATH)
verify_circus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_circus)
SHA = "a" * 40
REPO = "owner/project"


class VerifyCircusTest(unittest.TestCase):
    def setUp(self):
        self.env = {"GITHUB_SHA": "c" * 40, "GITHUB_REPOSITORY": REPO, "GH_TOKEN": "not-a-real-token",
                    "GITHUB_REF": "refs/heads/main", "EVENT_NAME": "workflow_dispatch", "PR_NUMBER": "42", "PR_SHA": SHA}
        self.pr = {"number": 42, "state": "open", "draft": False, "user": {"id": 123},
                   "base": {"ref": "main"}, "head": {"sha": SHA, "repo": {"full_name": REPO}}}
        self.status = [{"context": "circus/pr-artifacts", "state": "success", "creator": {"login": "circus-pschmitt[bot]"}}]

    def fetch(self, path, token):
        self.assertEqual(token, "not-a-real-token")
        if path == f"repos/{REPO}/pulls/42":
            return self.pr
        if path == f"repos/{REPO}/commits/{SHA}/statuses?per_page=100":
            return self.status
        raise AssertionError(path)

    def test_main_status_must_match_source_and_context(self):
        env = self.env | {"GITHUB_SHA": SHA, "EVENT_NAME": "status", "PR_NUMBER": "", "PR_SHA": "",
                          "STATUS_CONTEXT": "circus/artifacts", "STATUS_STATE": "success", "STATUS_SHA": SHA}
        verify_circus.verify(env, self.fetch)
        for change in [{"STATUS_SHA": "b" * 40}, {"STATUS_STATE": "pending"}, {"STATUS_CONTEXT": "other"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_circus.verify(env | change, self.fetch)

    def test_trusted_pr_with_successful_artifacts_is_accepted(self):
        verify_circus.verify(self.env, self.fetch)

    def test_untrusted_or_changed_pr_is_rejected(self):
        for field, value in [("state", "closed"), ("draft", True),
                             ("base", {"ref": "other"}),
                             ("head", {"sha": SHA, "repo": {"full_name": "foreign/project"}}),
                             ("head", {"sha": "b" * 40, "repo": {"full_name": REPO}})]:
            original = self.pr[field]
            self.pr[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                verify_circus.verify(self.env, self.fetch)
            self.pr[field] = original

    def test_missing_or_wrong_pr_status_is_rejected(self):
        for status in [[], [{"context": "circus/pr-artifacts", "state": "pending"}],
                       [{"context": "circus/artifacts", "state": "success"}],
                       [{"context": "circus/pr-artifacts", "state": "success", "creator": {"login": "other"}}]]:
            self.status = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                verify_circus.verify(self.env, self.fetch)

    def test_wrong_dispatch_identity_rejected_before_network(self):
        for change in [{"PR_SHA": "invalid"}, {"PR_NUMBER": "0"}, {"EVENT_NAME": "pull_request"}, {"GITHUB_REF": "refs/heads/feature"}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_circus.verify(self.env | change, lambda *_: self.fail("unexpected network request"))

    def test_latest_failed_status_cannot_be_overridden_by_older_success(self):
        self.status = [{"context": "circus/pr-artifacts", "state": "failure", "creator": {"login": "circus-pschmitt[bot]"}}, *self.status]
        with self.assertRaises(ValueError):
            verify_circus.verify(self.env, self.fetch)

    def test_public_metadata_falls_back_when_token_lacks_scope(self):
        error = HTTPError("https://api.github.com/test", 403, "forbidden", {}, None)

        class Response(io.BytesIO):
            pass
        with patch.object(verify_circus.urllib.request, "urlopen", side_effect=[error, Response(b'{"ok":true}')]) as call:
            self.assertEqual(verify_circus.fetch_json("test", "not-a-real-token"), {"ok": True})
        self.assertTrue(call.call_args_list[0].args[0].has_header("Authorization"))
        self.assertFalse(call.call_args_list[1].args[0].has_header("Authorization"))


if __name__ == "__main__":
    unittest.main()
