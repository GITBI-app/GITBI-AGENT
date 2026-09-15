import subprocess
import tempfile
import unittest
from pathlib import Path

from app.version import AGENT_NAME, AGENT_VERSION, get_version_info
from app.versioning import write_version_files


class VersionInfoTests(unittest.TestCase):
    def test_get_version_info_returns_name_and_version(self):
        self.assertEqual(
            get_version_info(),
            {"name": AGENT_NAME, "version": AGENT_VERSION},
        )

    def test_write_version_files_uses_git_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)
            (repo_root / "README.md").write_text("demo", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_root, check=True, capture_output=True)
            subprocess.run(["git", "tag", "v1.2.3"], cwd=repo_root, check=True)

            version_file = repo_root / "app" / "version.py"
            installer_file = repo_root / "installer" / "version.iss"
            version_file.parent.mkdir(parents=True, exist_ok=True)
            installer_file.parent.mkdir(parents=True, exist_ok=True)

            version = write_version_files(repo_root=str(repo_root), version_file_path=version_file, installer_file_path=installer_file)

            self.assertEqual(version, "v1.2.3")
            self.assertIn('AGENT_VERSION = "v1.2.3"', version_file.read_text(encoding="utf-8"))
            self.assertIn('#define AppVersion "v1.2.3"', installer_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
