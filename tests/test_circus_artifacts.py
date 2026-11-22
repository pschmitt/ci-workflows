"""A Circus artifact consumer must never fall back to a Nix build."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/nix-build.sh"


class CircusArtifactsTest(unittest.TestCase):
    def test_cache_only_disables_builds_and_ifd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nix = root / "nix"
            nix.write_text(r'''#!/usr/bin/env bash
set -euo pipefail
[[ "$1 $2 $3 $4 $5 $6 $7 $8 $9 ${10} ${11} ${12}" == \
  '--option max-jobs 0 --option builders  --option fallback false --option allow-import-from-derivation false' ]] || exit 31
shift 12
case "$1 $2" in
  'eval --impure') printf '%s\n' x86_64-linux ;;
  'eval --json') printf '%s\n' '["default"]' ;;
  'build --no-link') printf '%s\n' '/nix/store/11111111111111111111111111111111-example' ;;
  *) exit 32 ;;
esac
''')
            nix.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CIRCUS_CACHE_ONLY": "true",
                "OUTPUT_DIR": str(root / "out"),
                "SYSTEM": "x86_64-linux",
                "PACKAGES": '["default"]',
                "EXCLUDE": "[]",
            }
            result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/nix/store/", (root / "out/nix-paths").read_text())


if __name__ == "__main__":
    unittest.main()
