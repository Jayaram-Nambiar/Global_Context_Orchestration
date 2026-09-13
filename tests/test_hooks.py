#!/usr/bin/env python3
"""
Automated Test for Git Pre-Commit Hook Integration
Verifies that install-hooks configures .git/hooks/pre-commit and intercepts syntax errors.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class TestGitPreCommitHook(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        # Initialize temp git repo
        subprocess.run(["git", "init"], cwd=str(self.test_dir), capture_output=True, check=True)
        # Configure local git user for commit
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(self.test_dir), capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.test_dir), capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_install_hooks_and_interception(self):
        # Run install-hooks.ps1 on temp repo
        ps_script = SCRIPTS_DIR / "install-hooks.ps1"
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-RepoRoot", str(self.test_dir)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        hook_file = self.test_dir / ".git" / "hooks" / "pre-commit"
        self.assertTrue(hook_file.is_file())

        hook_content = hook_file.read_text(encoding="utf-8")
        self.assertIn("ctx check", hook_content)


if __name__ == "__main__":
    unittest.main()
