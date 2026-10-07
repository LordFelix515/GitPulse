import unittest
from pathlib import Path
import tempfile
import os
import shutil

from gitpulse import parse_user_selection
import ignore_manager
from startup_manager import get_windows_startup_dir


class TestAutoGithubLogic(unittest.TestCase):
    def test_parse_user_selection_single_download(self):
        action, indices = parse_user_selection("1", 5)
        self.assertEqual(action, "download")
        self.assertEqual(indices, [1])

    def test_parse_user_selection_multiple_download(self):
        action, indices = parse_user_selection("1 3", 5)
        self.assertEqual(action, "download")
        self.assertEqual(indices, [1, 3])

    def test_parse_user_selection_comma_download(self):
        action, indices = parse_user_selection("1, 3", 5)
        self.assertEqual(action, "download")
        self.assertEqual(indices, [1, 3])

    def test_parse_user_selection_single_ignore(self):
        action, indices = parse_user_selection("1 ignore", 5)
        self.assertEqual(action, "ignore")
        self.assertEqual(indices, [1])

    def test_parse_user_selection_multiple_ignore(self):
        action, indices = parse_user_selection("1 3 ignore", 5)
        self.assertEqual(action, "ignore")
        self.assertEqual(indices, [1, 3])

    def test_parse_user_selection_ignore_prefix(self):
        action, indices = parse_user_selection("ignore 1 3", 5)
        self.assertEqual(action, "ignore")
        self.assertEqual(indices, [1, 3])

    def test_parse_user_selection_all(self):
        action, indices = parse_user_selection("all", 4)
        self.assertEqual(action, "download")
        self.assertEqual(indices, [1, 2, 3, 4])

    def test_parse_user_selection_all_ignore(self):
        action, indices = parse_user_selection("all ignore", 3)
        self.assertEqual(action, "ignore")
        self.assertEqual(indices, [1, 2, 3])

    def test_parse_user_selection_skip(self):
        action, indices = parse_user_selection("", 5)
        self.assertEqual(action, "skip")
        self.assertEqual(indices, [])

    def test_ignore_manager(self):
        test_dir = Path(tempfile.mkdtemp())
        original_base = ignore_manager.get_base_dir
        try:
            ignore_manager.get_base_dir = lambda: test_dir
            added = ignore_manager.add_to_ignore(["my-test-repo", "another-repo"])
            self.assertEqual(len(added), 2)

            self.assertTrue(ignore_manager.is_repo_ignored("my-test-repo"))
            self.assertTrue(ignore_manager.is_repo_ignored("MY-TEST-REPO"))
            self.assertFalse(ignore_manager.is_repo_ignored("unknown-repo"))

            removed = ignore_manager.remove_from_ignore("my-test-repo")
            self.assertTrue(removed)
            self.assertFalse(ignore_manager.is_repo_ignored("my-test-repo"))
        finally:
            ignore_manager.get_base_dir = original_base
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_windows_startup_dir(self):
        startup_dir = get_windows_startup_dir()
        self.assertTrue(str(startup_dir).endswith("Startup"))

    def test_env_guard_backup_and_restore(self):
        from env_guard import backup_env_files, restore_env_files, find_env_files
        test_repo = Path(tempfile.mkdtemp())
        try:
            # .env dosyaları oluştur
            root_env = test_repo / ".env"
            root_env.write_text("DB_PASS=secret123\nAPI_KEY=xyz", encoding="utf-8")

            nested_dir = test_repo / "server"
            nested_dir.mkdir()
            nested_env = nested_dir / ".env.local"
            nested_env.write_text("PORT=3000", encoding="utf-8")

            # node_modules içinde olanlar taranmamalı
            nm_dir = test_repo / "node_modules" / "some_pkg"
            nm_dir.mkdir(parents=True)
            (nm_dir / ".env").write_text("SHOULD_BE_IGNORED", encoding="utf-8")

            found = find_env_files(test_repo)
            self.assertEqual(len(found), 2)

            # Yedekle
            backups = backup_env_files(test_repo)
            self.assertIn(".env", backups)
            self.assertIn("server\\.env.local" if os.name == "nt" else "server/.env.local", backups)

            # Dosyaları sil (git pull/reset simülasyonu)
            root_env.unlink()
            nested_env.unlink()
            self.assertFalse(root_env.exists())
            self.assertFalse(nested_env.exists())

            # Geri yükle
            restored = restore_env_files(test_repo, backups)
            self.assertEqual(len(restored), 2)
            self.assertTrue(root_env.exists())
            self.assertTrue(nested_env.exists())
            self.assertEqual(root_env.read_text(encoding="utf-8"), "DB_PASS=secret123\nAPI_KEY=xyz")
            self.assertEqual(nested_env.read_text(encoding="utf-8"), "PORT=3000")
        finally:
            shutil.rmtree(test_repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
