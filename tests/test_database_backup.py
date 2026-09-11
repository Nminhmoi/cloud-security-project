import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.database_backup import (
    backup_database,
    restore_database,
    verify_database,
)


class DatabaseBackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source.db"
        with closing(sqlite3.connect(self.source)) as connection:
            connection.execute("CREATE TABLE records (value TEXT NOT NULL)")
            connection.execute("INSERT INTO records VALUES ('before-backup')")
            connection.commit()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_backup_is_consistent_and_restore_creates_new_database(self):
        backup = self.root / "backups" / "snapshot.db"
        backup_path, checksum = backup_database(self.source, backup)
        self.assertEqual(len(checksum), 64)
        self.assertEqual(verify_database(backup_path), backup.resolve())

        with closing(sqlite3.connect(self.source)) as connection:
            connection.execute("UPDATE records SET value = 'after-backup'")
            connection.commit()

        restored = self.root / "restored.db"
        restore_database(backup, restored)
        with closing(sqlite3.connect(restored)) as connection:
            value = connection.execute("SELECT value FROM records").fetchone()[0]
        self.assertEqual(value, "before-backup")

    def test_backup_and_restore_refuse_to_overwrite(self):
        destination = self.root / "existing.db"
        destination.write_bytes(b"do-not-overwrite")
        with self.assertRaises(FileExistsError):
            backup_database(self.source, destination)
        with self.assertRaises(FileExistsError):
            restore_database(self.source, destination)
        self.assertEqual(destination.read_bytes(), b"do-not-overwrite")

    def test_verify_rejects_non_database_file(self):
        invalid = self.root / "invalid.db"
        invalid.write_text("not sqlite", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_database(invalid)


if __name__ == "__main__":
    unittest.main()
